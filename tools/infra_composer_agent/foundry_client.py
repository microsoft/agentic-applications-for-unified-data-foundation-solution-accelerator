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

Two invocation styles are available:

  * `call_responses` -- a raw, unbound model call: `model` + `instructions`
    are sent directly on every request, with no registered Foundry Agent
    involved at all. Kept for callers that don't want a persisted agent
    identity.

  * `ensure_agent` + `call_agent` -- the REAL registered-Foundry-Agent
    path, used by this project's two actual LLM calls (the "Planner" agent
    in conversational_planner.py, and the "Infra-Builder" agent in
    llm_composer.py). `ensure_agent` publishes/updates a named
    `PromptAgentDefinition` (model + instructions) via
    `project.agents.create_version` -- run once at the start of every use
    so the registered agent's instructions always match whatever the
    current skill markdown file on disk says, the same freshness guarantee
    the old raw-call approach had. `call_agent` then gets an OpenAI client
    BOUND to that agent name (`project.get_openai_client(agent_name=...)`)
    and calls `responses.create(...)` on it -- the agent's own registered
    model/instructions apply server-side; the caller only ever sends the
    user/assistant conversation turns, never `model`/`instructions` again.
    This is genuinely running "as" a named Foundry Agent, visible/
    addressable in the AI Foundry portal's Agents tab, not just a
    portal-visibility registration that the real calls ignore.
"""
from __future__ import annotations

# Cache OpenAI clients per (project_endpoint, agent_name) so repeated calls
# within one run (e.g. every self-correction retry attempt) don't
# re-authenticate/re-bind each time. agent_name is None for the
# non-agent-bound client (kept for any caller that still wants a raw
# model+instructions call via call_responses()).
_client_cache: dict[tuple[str, str | None], object] = {}


def get_openai_client(project_endpoint: str, agent_name: str | None = None):
    """Returns (and caches) a standard OpenAI client authenticated against the
    given Azure AI Foundry project endpoint, via azure-ai-projects'
    AIProjectClient.get_openai_client() -- the same mechanism CAIRA's
    foundry-client.ts uses (`project.getOpenAIClient()`).

    When `agent_name` is given, the returned client is bound to that
    registered Foundry Agent (`project.get_openai_client(agent_name=...)`) --
    every `responses.create(...)` call made with it runs AS that agent (the
    agent's own registered model + instructions apply), instead of a raw,
    unbound model call."""
    cache_key = (project_endpoint, agent_name)
    cached = _client_cache.get(cache_key)
    if cached is not None:
        return cached
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    project = AIProjectClient(endpoint=project_endpoint, credential=DefaultAzureCredential())
    client = project.get_openai_client(agent_name=agent_name) if agent_name else project.get_openai_client()
    _client_cache[cache_key] = client
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
    Foundry agent definition, mirroring CAIRA's foundry-client.ts
    registerAgents() get-or-create pattern (project.agents.get(), then
    project.agents.create_version() to publish -- create_version() creates
    the agent itself if `agent_name` doesn't exist yet, and a new version if
    it does). Returns a short status string for logging.

    This is the low-level primitive `ensure_agent` below wraps for the
    project's real, agent-bound calls (call_agent) -- it's also still usable
    standalone (see update_agent_instructions.py) purely for portal
    visibility/governance when a caller only wants the definition published,
    without necessarily calling through it."""
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


# Tracks which (project_endpoint, agent_name) pairs have already been
# ensure_agent()-ed THIS PROCESS, so a run with many retry-loop calls (e.g.
# generate_main_bicep_with_llm's self-correction attempts) only republishes
# the agent definition once per run, not once per attempt.
_ensured_agents: set[tuple[str, str]] = set()


def ensure_agent(project_endpoint: str, agent_name: str, model: str, instructions: str) -> None:
    """Publishes/updates the named agent's definition (model + instructions)
    exactly once per (endpoint, agent_name) for the lifetime of this
    process, then no-ops on subsequent calls. Callers should invoke this
    once at the start of a conversation/generation run, BEFORE the first
    call_agent(...) call, so the registered agent's instructions always
    reflect whatever the current skill markdown file on disk says right
    now -- the same "always fresh, edit-the-markdown-not-the-code"
    guarantee the old raw call_responses() path had, now carried over to a
    real registered agent instead of a per-call instructions string.
    Registration failures are NOT swallowed here (unlike register_agent's
    own callers in update_agent_instructions.py) -- if the agent can't be
    published, call_agent would otherwise run against a stale or
    nonexistent agent definition, which is worse than failing loudly."""
    key = (project_endpoint, agent_name)
    if key in _ensured_agents:
        return
    register_agent(project_endpoint, agent_name, model, instructions)
    _ensured_agents.add(key)


def call_agent(messages: list[dict], project_endpoint: str, agent_name: str,
                extra_instructions: str | None = None) -> str:
    """Runs one turn AS a registered Foundry Agent (call ensure_agent(...)
    first so the agent's published instructions are current). Unlike
    call_responses, `model` and `instructions` are never sent by the
    caller -- they come from the agent's own registered definition,
    resolved server-side by Azure AI Foundry from `agent_name`. Any
    `{"role": "system", ...}` message in `messages` is dropped (the agent's
    registered instructions supersede it); all other messages are sent as
    `input` verbatim, same shape as call_responses.

    `extra_instructions`, if given, is passed as a per-call `instructions`
    override alongside the agent binding -- useful for a one-off sub-task
    (e.g. the Planner agent's technical-pattern-matching step, which needs
    a different, narrower instruction set than its main planning
    instructions for that single call) without registering a second agent
    for it. NOTE: whether a per-call `instructions` value supplements or
    fully overrides an agent-bound client's own registered instructions is
    Foundry Agent Service behavior that could not be verified against a
    live project in this environment -- treat this parameter as best-effort;
    if it turns out not to take precedence, the call still runs (just under
    the agent's default instructions) rather than failing."""
    client = get_openai_client(project_endpoint, agent_name=agent_name)

    input_items = []
    for m in messages:
        if m["role"] == "system":
            continue
        input_items.append({"role": m["role"], "content": m["content"]})

    kwargs = {"input": input_items}
    if extra_instructions:
        kwargs["instructions"] = extra_instructions

    response = client.responses.create(**kwargs)
    text = (response.output_text or "").strip()
    if not text:
        raise RuntimeError(f"No assistant response text found in the '{agent_name}' agent's Responses API result")
    return text
