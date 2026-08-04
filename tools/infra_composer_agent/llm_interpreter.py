"""
Optional LLM-assisted prompt interpretation, backed by an Azure AI Foundry
agent.

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
  * If Azure AI Foundry isn't configured (no endpoint/credentials), or the
    optional SDK isn't installed, or any call fails for any reason, this
    module returns None and the caller falls back to the plain deterministic
    matcher. LLM assistance is strictly additive, never a hard dependency.

Configuration (all optional; env vars used if CLI flags are omitted):
  AI_FOUNDRY_PROJECT_ENDPOINT   e.g. https://<project>.services.ai.azure.com/api/projects/<project-name>
  AI_FOUNDRY_MODEL_DEPLOYMENT   e.g. gpt-4o  (name of a model deployed in that project)
  AI_FOUNDRY_AGENT_ID           optional: reuse an existing persistent agent instead of
                                creating/deleting a temporary one each run.

Requires (only if you actually want to use this):
    pip install azure-ai-projects azure-identity
Auth uses DefaultAzureCredential (e.g. `az login` locally, or a managed
identity/service principal in CI).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from module_index import ModuleInfo
from request_parser import ResourceRequest, _tokenize, score_module

AGENT_INSTRUCTIONS = """You are an infrastructure request interpreter for an Azure Bicep composition \
agent. You will be given (1) a natural-language infrastructure request and (2) a catalog of the \
ONLY resource concepts that actually exist as reusable modules. Your job is only to identify \
which concepts from the catalog are being requested, how many of each, and any relationships \
between them (role assignments / RBAC, connections, dependencies) that the request implies. \

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
    """Creates (or reuses) an Azure AI Foundry agent and runs one turn.
    Raises on any failure -- caller is responsible for catching and
    falling back to the deterministic matcher."""
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    client = AIProjectClient(endpoint=project_endpoint, credential=DefaultAzureCredential())
    agents_client = client.agents

    created_agent_id = None
    try:
        if agent_id:
            active_agent_id = agent_id
        else:
            agent = agents_client.create_agent(
                model=model_deployment,
                name="infra-composer-prompt-interpreter",
                instructions=AGENT_INSTRUCTIONS,
            )
            active_agent_id = agent.id
            created_agent_id = agent.id

        thread = agents_client.threads.create()
        agents_client.messages.create(thread_id=thread.id, role="user", content=prompt_text)
        run = agents_client.runs.create_and_process(thread_id=thread.id, agent_id=active_agent_id)

        if run.status == "failed":
            raise RuntimeError(f"Agent run failed: {getattr(run, 'last_error', run)}")

        messages = list(agents_client.messages.list(thread_id=thread.id))
        for msg in messages:
            if msg.role == "assistant" and msg.content:
                for part in msg.content:
                    text_val = getattr(getattr(part, "text", None), "value", None)
                    if text_val:
                        return text_val
        raise RuntimeError("No assistant response found in thread")
    finally:
        if created_agent_id:
            try:
                agents_client.delete_agent(created_agent_id)
            except Exception:
                pass  # best-effort cleanup; never fail the run over this


def interpret_with_llm(prompt: str, modules: list[ModuleInfo], project_endpoint: str,
                        model_deployment: str, agent_id: str | None = None) -> list[ResourceRequest] | None:
    """Returns a list of ResourceRequest (matched against the real module
    index, same as the deterministic path) or None if LLM assistance is
    unavailable/failed for any reason."""
    try:
        catalog = _build_catalog_text(modules)
        full_prompt = f"Available module catalog:\n{catalog}\n\nUser request:\n{prompt}"
        raw = _call_ai_foundry_agent(full_prompt, project_endpoint, model_deployment, agent_id)
        parsed = _extract_json(raw)
    except Exception as exc:  # noqa: BLE001 - deliberately broad: any failure -> fallback
        print(f"LLM interpretation unavailable/failed ({exc.__class__.__name__}: {exc}); "
              f"falling back to deterministic matching.")
        return None

    requests: list[ResourceRequest] = []
    for item in parsed.get("resources", []):
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
    return requests or None
