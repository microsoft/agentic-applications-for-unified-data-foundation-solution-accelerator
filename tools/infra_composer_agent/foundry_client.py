"""
Shared Azure AI Foundry client helpers -- the NEW Responses/Conversations
API pattern (azure-ai-projects >= 2.4 + openai), replacing the OLD
Threads/Runs Assistants-style `azure-ai-agents` pattern this project used
previously (manual client.threads.create() / client.messages.create() /
client.runs.create_and_process() / poll client.messages.list()).

Modeled directly on microsoft/CAIRA's reference implementation
(reference-architectures/app/api/typescript/foundry-agent-service/src/
foundry-client.ts): `AIProjectClient.get_openai_client()` returns a
standard OpenAI client authenticated against the Foundry project
endpoint, and every model call goes through a single
`openai.responses.create(...)` call instead of a multi-step thread/run
lifecycle.

Why the switch:
  * One HTTP round-trip per turn instead of four (create thread, create
    message, create-and-poll run, list messages).
  * `instructions` is a first-class field -- no need to smuggle the system
    prompt in as a fake message.
  * This is the API surface Azure AI Foundry is investing in going
    forward; Threads/Runs (Assistants API) is the legacy pattern.

Agent registration (`register_agent` below, using `project.agents.get` /
`project.agents.create_version`) is OPTIONAL -- it only publishes an agent
definition so it's visible/inspectable in the AI Foundry portal's Agents
tab for governance/audit purposes, exactly like CAIRA's `registerAgents()`.
The actual model calls (`call_responses`) never reference that registered
agent by ID/name; they send `model` + `instructions` directly on every
call, matching CAIRA's own foundry-client.ts (which also passes
model/instructions/tools per-call rather than routing through the
registered agent's ID). This project doesn't need server-side thread
state either -- callers already keep the full message history in memory
across self-correction retries and simply replay it as `input` each call.
"""
from __future__ import annotations

# Cache OpenAI clients per project endpoint so repeated calls within one run
# (e.g. every self-correction retry attempt) don't re-authenticate each time.
_client_cache: dict[str, object] = {}


def get_openai_client(project_endpoint: str):
    """Returns (and caches) a standard OpenAI client authenticated against the
    given Azure AI Foundry project endpoint, via azure-ai-projects'
    AIProjectClient.get_openai_client() -- the same mechanism CAIRA's
    foundry-client.ts uses (`project.getOpenAIClient()`)."""
    cached = _client_cache.get(project_endpoint)
    if cached is not None:
        return cached
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    project = AIProjectClient(endpoint=project_endpoint, credential=DefaultAzureCredential())
    client = project.get_openai_client()
    _client_cache[project_endpoint] = client
    return client


def call_responses(messages: list[dict], project_endpoint: str, model: str | None) -> str:
    """Runs one turn via the Responses API (openai.responses.create) -- the
    replacement for this project's old thread/run helpers
    (_call_ai_foundry_chat in llm_composer.py, _call_ai_foundry_agent in
    llm_interpreter.py). `messages` is the same [{"role": ..., "content":
    ...}, ...] shape callers already build for self-correction retries: the
    system message (if present) is sent as `instructions`, everything else
    as `input`. Raises RuntimeError with a clear message on any failure or
    misconfiguration -- there is no fallback."""
    if not model:
        raise RuntimeError(
            "This call requires --ai-foundry-model (or AI_FOUNDRY_MODEL_DEPLOYMENT). "
            "The Responses API sends the model deployment name on every call -- unlike "
            "the old Assistants-style agents, there's no pre-created agent with a model "
            "already baked in."
        )
    client = get_openai_client(project_endpoint)

    instructions = None
    input_items = []
    for m in messages:
        if m["role"] == "system":
            instructions = m["content"]
        else:
            input_items.append({"role": m["role"], "content": m["content"]})

    response = client.responses.create(model=model, instructions=instructions, input=input_items)
    text = (response.output_text or "").strip()
    if not text:
        raise RuntimeError("No assistant response text found in the Responses API result")
    return text


def register_agent(project_endpoint: str, agent_name: str, model: str, instructions: str) -> str:
    """Registers (creates, or publishes a new version of) a persistent
    Foundry agent definition -- purely for portal visibility/governance,
    mirroring CAIRA's foundry-client.ts registerAgents() get-or-create
    pattern (project.agents.get(), then project.agents.create_version() to
    publish -- create_version() creates the agent itself if `agent_name`
    doesn't exist yet, and a new version if it does). This project's actual
    model calls (call_responses above) never reference this registration --
    it's safe for callers to treat failures here as non-fatal warnings.
    Returns a short status string for logging."""
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import PromptAgentDefinition
    from azure.core.exceptions import ResourceNotFoundError
    from azure.identity import DefaultAzureCredential

    project = AIProjectClient(endpoint=project_endpoint, credential=DefaultAzureCredential())
    definition = PromptAgentDefinition(model=model, instructions=instructions)

    try:
        project.agents.get(agent_name)
        status = "updated"
    except ResourceNotFoundError:
        status = "created"
    project.agents.create_version(agent_name, definition=definition)
    return f"{status} agent '{agent_name}' ({len(instructions)} chars of instructions, model={model})"
