"""
LLM-assisted prompt interpretation.

Why this exists: the deterministic matcher in request_parser.py works well
for simple, resource-shaped prompts ("2 storage accounts and 1 app
service"), but real prompts are messier and more intent-driven, e.g.
    "assign the Cognitive Services User role to the AI service so it can
     call the AI Foundry project, and set up the connection between them"
There is no clean 1:1 noun-phrase -> module mapping here: the LLM needs to
figure out *which resources and relationships* (role assignments,
connections/private endpoints, RBAC) are actually being asked for, then
hand back a small structured list this agent's existing deterministic
pipeline can safely consume.

Design constraints (important -- do not relax these):
  * The LLM NEVER generates Bicep, never invents module paths, and never
    picks parameter values. It only proposes *which resource concepts* (as
    free-text, matched against the real module catalog by the existing
    fuzzy matcher) and *what relationships* (role assignments / connections)
    are implied. All actual module selection, dependency resolution, and
    code generation stays in the deterministic pipeline
    (request_parser.py / resolver.py / composer.py), so the agent can never
    hallucinate a non-existent module or broken reference.

Backend: runs via a PERSISTENT Azure AI Foundry agent (created once with
azure-ai-agents' AgentsClient.create_agent, visible in the AI Foundry
portal's Agents tab as "infra-composer-prompt-interpreter"). Every call
opens a real thread, posts a user message, and runs that agent -- not a
stateless chat completion. Defaults to DEFAULT_INTERPRETER_AGENT_ID below;
pass --ai-foundry-agent-id to point at a different existing agent.

Configuration (all optional; env vars used if CLI flags are omitted):
  AI_FOUNDRY_PROJECT_ENDPOINT   e.g. https://<project>.services.ai.azure.com/api/projects/<project-name>
  AI_FOUNDRY_MODEL_DEPLOYMENT   only used when creating a NEW agent (the model is already
                                baked into DEFAULT_INTERPRETER_AGENT_ID's config; unused
                                once you have an existing agent_id).
  AI_FOUNDRY_AGENT_ID           override to reuse a different existing persistent agent
                                instead of DEFAULT_INTERPRETER_AGENT_ID.

Requires:
    pip install azure-ai-agents azure-identity
Auth uses DefaultAzureCredential (e.g. `az login` locally, or a managed
identity/service principal in CI).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from module_index import ModuleInfo
from request_parser import ResourceRequest, _tokenize, score_module

INTERPRETER_INSTRUCTIONS = """You are an infrastructure request interpreter for an Azure Bicep composition \
agent. You will be given (1) a natural-language infrastructure request and (2) a catalog of the \
ONLY resource concepts that actually exist as reusable modules. Your job is only to identify \
which concepts from the catalog are being requested, how many of each, and any relationships \
between them (role assignments / RBAC, connections, dependencies) that the request implies.

Rules:
- Only ever refer to concepts that are clearly implied by the request. Do not invent resources \
that were not asked for or implied.
- Prefer matching against the given catalog's wording; if the request describes something not in \
the catalog (e.g. a specific role name), still include the closest resource concept (e.g. \
"role assignment") and put the specific detail (e.g. the role name, source, target) in "detail".
- Output STRICT JSON ONLY, no markdown fences, no commentary, matching exactly this schema:
{
  "resources": [
    {"concept": "<short free-text concept, e.g. 'ai service', 'role assignment', 'private endpoint'>",
     "count": <integer, default 1>,
     "detail": "<optional short free-text note, e.g. 'Cognitive Services User role from AI Service to AI Foundry project'>"}
  ]
}
Return nothing except that JSON object.
"""

# Persistent AI Foundry agent, created once in the project (proj-default) so every
# run reuses the same registered agent instead of creating/deleting a temp one.
# Visible in the AI Foundry portal's Agents tab as "infra-composer-prompt-interpreter".
DEFAULT_INTERPRETER_AGENT_ID = "asst_grJbGnsVfPJu0YfHFbubrhCG"


@dataclass
class LlmInterpretation:
    raw_response: str
    resources: list[dict]


def _build_catalog_text(modules: list[ModuleInfo]) -> str:
    lines = []
    for m in modules:
        lines.append(f"- {m.key}: tags=[{', '.join(sorted(m.tags))}]")
    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    text = text.strip()
    # Strip accidental markdown fences if the model adds them anyway.
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE | re.MULTILINE)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(match.group(0))


def _call_ai_foundry_agent(prompt_text: str, project_endpoint: str, model_deployment: str,
                            agent_id: str | None) -> str:
    """Runs one turn against a PERSISTENT Azure AI Foundry agent (created once via
    azure-ai-agents' AgentsClient.create_agent -- visible in the AI Foundry portal's
    Agents tab) using the real thread/message/run lifecycle, not a stateless chat
    completion. Defaults to the pre-created interpreter agent
    (DEFAULT_INTERPRETER_AGENT_ID) unless a different agent_id is supplied. Raises on
    any failure -- no fallback."""
    from azure.ai.agents import AgentsClient
    from azure.identity import DefaultAzureCredential

    active_agent_id = agent_id or DEFAULT_INTERPRETER_AGENT_ID
    client = AgentsClient(endpoint=project_endpoint, credential=DefaultAzureCredential())

    thread = client.threads.create()
    client.messages.create(thread_id=thread.id, role="user", content=prompt_text)
    run = client.runs.create_and_process(thread_id=thread.id, agent_id=active_agent_id)

    if run.status != "completed":
        raise RuntimeError(f"Agent run did not complete (status={run.status}): {getattr(run, 'last_error', '')}")

    for msg in client.messages.list(thread_id=thread.id):
        if msg.role == "assistant" and msg.content:
            for part in msg.content:
                text_val = getattr(getattr(part, "text", None), "value", None)
                if text_val:
                    return text_val
    raise RuntimeError("No assistant response found in thread")


def _resources_to_requests(resources: list[dict], modules: list[ModuleInfo]) -> list[ResourceRequest]:
    requests: list[ResourceRequest] = []
    for item in resources:
        concept = str(item.get("concept", "")).strip()
        if not concept:
            continue
        count = int(item.get("count", 1) or 1)
        detail = str(item.get("detail", "") or "")
        text = f"{concept} ({detail})" if detail else concept
        tokens = _tokenize(concept)
        if not tokens:
            continue
        best_score = 0.0
        tied: list[ModuleInfo] = []
        for module in modules:
            s = score_module(tokens, module)
            if s > best_score:
                best_score = s
                tied = [module]
            elif s == best_score and s > 0:
                tied.append(module)
        best_module = max(tied, key=lambda m: m.name) if tied else None
        requests.append(ResourceRequest(text=text, count=count, tokens=tokens,
                                         matched_module=best_module, score=best_score))
    return requests


def interpret_with_llm(prompt: str, modules: list[ModuleInfo],
                        project_endpoint: str | None = None, model_deployment: str | None = None,
                        agent_id: str | None = None) -> list[ResourceRequest]:
    """Returns a list of ResourceRequest (matched against the real module
    index) using the persistent Azure AI Foundry interpreter agent. Raises
    RuntimeError with a clear message if the backend is unavailable/
    misconfigured or the call fails -- callers that want a hard requirement
    (no silent fallback) should let this propagate."""
    if not project_endpoint:
        raise RuntimeError(
            "AI Foundry interpretation requires --ai-foundry-endpoint (or AI_FOUNDRY_PROJECT_ENDPOINT). "
            "model_deployment is only needed if you're creating a brand-new agent -- the "
            "default persistent agent already has a model configured."
        )
    catalog = _build_catalog_text(modules)
    full_prompt = f"Available module catalog:\n{catalog}\n\nUser request:\n{prompt}"
    raw = _call_ai_foundry_agent(full_prompt, project_endpoint, model_deployment, agent_id)

    parsed = _extract_json(raw)
    resources = parsed.get("resources", [])
    requests = _resources_to_requests(resources, modules)
    # An empty "resources": [] is a legitimate answer (e.g. the leftover free
    # text after a technical pattern already covers everything, or a prompt
    # with nothing left to add) -- only raise when the LLM's response could
    # not even be parsed into the expected shape, since that indicates a real
    # backend/formatting failure rather than "nothing more to add".
    if not requests and not resources and "resources" not in parsed:
        raise RuntimeError(
            f"AI Foundry backend returned an unparseable response (no 'resources' key found): {raw!r}"
        )
    return requests
