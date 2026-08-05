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

Backends supported (pick with --llm-backend, default "ollama"):
  * "ollama"      -- runs fully locally via a local Ollama server
                     (http://localhost:11434 by default). Free, offline, no
                     API key/account. Install: https://ollama.com, then
                     `ollama pull llama3.1:8b` (or any other local model).
                     This is the primary/default backend -- no cloud
                     account is required to use --use-llm.
  * "ai-foundry"  -- runs via a hosted Azure AI Foundry agent (optional,
                     for when you want a larger hosted model instead of a
                     local one). Needs an existing AI Foundry project.

Configuration (all optional; env vars used if CLI flags are omitted):
  OLLAMA_HOST                   default: http://localhost:11434
  OLLAMA_MODEL                  default: llama3.1:8b
  AI_FOUNDRY_PROJECT_ENDPOINT   e.g. https://<project>.services.ai.azure.com/api/projects/<project-name>
  AI_FOUNDRY_MODEL_DEPLOYMENT   e.g. gpt-4o  (name of a model deployed in that project)
  AI_FOUNDRY_AGENT_ID           optional: reuse an existing persistent agent instead of
                                creating/deleting a temporary one each run.

The ai-foundry backend requires (only if you actually use it):
    pip install azure-ai-projects azure-identity
Auth uses DefaultAzureCredential (e.g. `az login` locally, or a managed
identity/service principal in CI). The ollama backend requires no extra
Python packages -- it talks to the local Ollama HTTP API with stdlib
urllib.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
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

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.1:8b"


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


def _call_ollama(prompt_text: str, host: str, model: str) -> str:
    """Calls a local Ollama server's chat endpoint. Raises on any failure
    (server not running, model not pulled, network error, etc.) -- caller
    decides how to handle it."""
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": INTERPRETER_INSTRUCTIONS},
            {"role": "user", "content": prompt_text},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }).encode("utf-8")
    req = urllib.request.Request(
        url=f"{host.rstrip('/')}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Could not reach local Ollama server at {host} ({exc}). "
            f"Is Ollama running? Start it, then `ollama pull {model}`."
        ) from exc
    content = body.get("message", {}).get("content")
    if not content:
        raise RuntimeError(f"Ollama returned no message content: {body}")
    return content


def _call_ai_foundry_agent(prompt_text: str, project_endpoint: str, model_deployment: str,
                            agent_id: str | None) -> str:
    """Creates (or reuses) an Azure AI Foundry agent and runs one turn.
    Raises on any failure."""
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
                instructions=INTERPRETER_INSTRUCTIONS,
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


def interpret_with_llm(prompt: str, modules: list[ModuleInfo], backend: str = "ollama",
                        ollama_host: str = DEFAULT_OLLAMA_HOST, ollama_model: str = DEFAULT_OLLAMA_MODEL,
                        project_endpoint: str | None = None, model_deployment: str | None = None,
                        agent_id: str | None = None) -> list[ResourceRequest]:
    """Returns a list of ResourceRequest (matched against the real module
    index). Raises RuntimeError with a clear message if the requested
    backend is unavailable/misconfigured or the call fails -- callers that
    want a hard requirement (no silent fallback) should let this propagate."""
    catalog = _build_catalog_text(modules)
    full_prompt = f"Available module catalog:\n{catalog}\n\nUser request:\n{prompt}"

    if backend == "ollama":
        raw = _call_ollama(full_prompt, ollama_host, ollama_model)
    elif backend == "ai-foundry":
        if not project_endpoint or not model_deployment:
            raise RuntimeError(
                "backend='ai-foundry' requires project_endpoint and model_deployment "
                "(--ai-foundry-endpoint / --ai-foundry-model or AI_FOUNDRY_PROJECT_ENDPOINT / "
                "AI_FOUNDRY_MODEL_DEPLOYMENT)."
            )
        raw = _call_ai_foundry_agent(full_prompt, project_endpoint, model_deployment, agent_id)
    else:
        raise RuntimeError(f"Unknown LLM backend '{backend}'. Use 'ollama' or 'ai-foundry'.")

    parsed = _extract_json(raw)
    requests = _resources_to_requests(parsed.get("resources", []), modules)
    if not requests:
        raise RuntimeError(
            f"LLM backend '{backend}' returned no usable resource concepts from response: {raw!r}"
        )
    return requests
