"""
LLM-based main.bicep generator.

Why this exists: the deterministic generator in composer.py produces a
correct-but-bare orchestrator (one `module` block per resolved module,
core params, a fallback param whenever something can't be auto-wired).
Real hand-authored orchestrators (see infra/avm/main.bicep in this repo)
are much richer: WAF feature flags (enableMonitoring/enablePrivateNetworking/
enableScalability/enableRedundancy), existing-vs-new conditionals, tags
merging via union(), enableTelemetry threaded through every module,
diagnostic settings wiring, deployer()-based tag metadata, and modules
named/conditioned to reflect real intent rather than a flat 1:1 dump.

This module asks an LLM (Ollama locally, or a PERSISTENT Azure AI Foundry
agent named "infra-composer-main-bicep-author" -- see DEFAULT_AUTHOR_AGENT_ID)
to actually *author* the main.bicep body -- reasoning about the request the
way an infrastructure architect would -- while staying safe:
  * The LLM is given the REAL resolved modules (exact relative paths,
    exact required/optional params, exact outputs) parsed by module_index.py.
    It cannot invent a module path or a parameter name that doesn't exist,
    because it's instructed to only use what's in that list.
  * Every attempt is validated with `az bicep build` before being accepted.
    If validation fails, the error output is fed back to the model for a
    self-correction retry (up to `max_attempts` times).
  * If the LLM still cannot produce a file that validates after all
    attempts, the caller (agent.py) falls back to the deterministic
    generator -- this is a *correctness safety net*, not a "backend
    fallback": the project's core success criterion is that the output
    must always be deployable without manual edits, so shipping unvalidated
    LLM output is never acceptable.

With --llm-backend ai-foundry, every call opens a real thread against the
persistent author agent (visible in the AI Foundry portal's Agents tab) and
replays prior attempts/errors into that thread for retries -- not a
stateless chat completion.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from module_index import ModuleInfo
from resolver import ResolutionResult
from bicep_validate import validate_with_az

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.1:8b"

# Persistent AI Foundry agent, created once in the project (proj-default) so every
# run reuses the same registered agent instead of creating/deleting a temp one.
# Visible in the AI Foundry portal's Agents tab as "infra-composer-main-bicep-author".
DEFAULT_AUTHOR_AGENT_ID = "asst_XTQ6h2DoCHJMorowBAg9gJZb"

STYLE_GUIDE = """Follow these authoring conventions (matching this repo's hand-written orchestrators):
- Start with a header comment block describing the file as a pure orchestrator.
- targetScope = 'resourceGroup'
- Core params: solutionName (string, @minLength(3) @maxLength(20), default 'composedsolution'),
  location (default resourceGroup().location), tags (object, default {}),
  enableTelemetry (bool, default true).
- Add WAF feature flag params where relevant to the requested resources, each defaulting to false:
  enableMonitoring, enablePrivateNetworking, enableRedundancy, enableScalability. Only include a flag
  if at least one selected module's behavior can meaningfully depend on it (e.g. only add
  enablePrivateNetworking if a private-endpoint/networking module is present).
- Derive a var solutionSuffix from solutionName (lowercased, special characters stripped) and pass
  it as the `solutionName` param into every module instead of the raw input param, exactly like:
  var solutionSuffix = toLower(trim(replace(replace(replace(replace(replace(replace('${solutionName}', '-', ''), '_', ''), '.', ''), '/', ''), ' ', ''), '*', '')))
- Merge caller tags with resourceGroup().tags using union(), e.g.:
  var resourceTags = union(resourceGroup().tags ?? {}, tags, {})
- Thread enableTelemetry into every module call that declares it as a param.
- Give each module block a deterministic name: name: take('module.<module-file-stem>.${solutionName}', 64)
- Wire dependent params to upstream module outputs using the `!` non-null assertion, e.g.
  workspaceResourceId: enableMonitoring ? logAnalytics!.outputs.resourceId : ''
  Only reference a module's outputs when that module is unconditionally created, or guard the
  reference with the same condition that guards the producing module.
- Conditionally create a module with `if (...)` only when there is a genuine reason to (a relevant
  feature flag, or an "existing vs new" pattern) -- otherwise create it unconditionally.
- ALWAYS pass every required parameter for every module (no exceptions) -- required params have no
  default and Bicep will fail to build if omitted.
- End with an Outputs section exposing the resourceId/name/endpoint (whichever the module actually
  outputs) of each top-level resource that was explicitly requested by the user.
- Reference modules by their exact relative path as given (e.g. './modules/compute/app-service.bicep').
- Do not invent parameters, outputs, or module paths that are not in the provided module list.
"""

SYSTEM_PROMPT = f"""You are an expert Azure Bicep infrastructure architect. You write a single, deployable
`main.bicep` orchestrator that composes ONLY the exact pre-existing local Bicep modules given to you --
you never invent a module, parameter, or output that isn't in the list provided. You reason about the
user's request like an architect: which feature flags make sense, how outputs should feed into
dependent parameters, and what makes a clean, idiomatic, production-style orchestrator.

{STYLE_GUIDE}

Respond with ONLY the raw Bicep code for main.bicep. No markdown fences, no commentary, no explanation
-- just the file content, starting with the header comment and ending with the last output statement.
"""


def _format_param(p) -> str:
    req = "REQUIRED" if p.required else f"optional, default={p.default}"
    desc = f" -- {p.description}" if p.description else ""
    return f"    - {p.name}: {p.type} ({req}){desc}"


def _module_catalog_text(resolution: ResolutionResult) -> str:
    lines = []
    for key, module in resolution.modules.items():
        rel = f"./modules/{module.rel_path.as_posix()}"
        requested = " [EXPLICITLY REQUESTED BY USER]" if key in resolution.explicitly_requested else " [auto-included dependency]"
        lines.append(f"- Module path: {rel}{requested}")
        lines.append(f"  Params:")
        for p in module.params:
            lines.append(_format_param(p))
        lines.append(f"  Outputs: {', '.join(o.name for o in module.outputs) or '(none)'}")
    return "\n".join(lines)


def build_generation_prompt(user_prompt: str, resolution: ResolutionResult, requested_counts: dict[str, int]) -> str:
    catalog = _module_catalog_text(resolution)
    counts_text = "\n".join(f"- {k}: requested count = {v}" for k, v in requested_counts.items())
    return (
        f"User's infrastructure request:\n{user_prompt}\n\n"
        f"Resolved modules available to use (exact paths/params/outputs -- use only these, "
        f"and use ALL of them):\n{catalog}\n\n"
        f"Requested instance counts (create this many `module` blocks for these, numbering symbol "
        f"names 1..N and their `name` params, if count > 1):\n{counts_text}\n\n"
        f"Write the complete main.bicep now."
    )


def _extract_bicep(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:bicep)?\s*\n(.*?)```", text, re.DOTALL)
    if fence:
        return fence.group(1).strip() + "\n"
    return text + ("\n" if not text.endswith("\n") else "")


def _call_ollama_chat(messages: list[dict], host: str, model: str) -> str:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.2},
    }).encode("utf-8")
    req = urllib.request.Request(
        url=f"{host.rstrip('/')}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
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


def _call_ai_foundry_chat(messages: list[dict], project_endpoint: str, model_deployment: str,
                           agent_id: str | None) -> str:
    """Runs one turn against a PERSISTENT Azure AI Foundry agent (created once via
    azure-ai-agents' AgentsClient.create_agent -- visible in the AI Foundry portal's
    Agents tab, instructions = SYSTEM_PROMPT/STYLE_GUIDE) using the real thread/
    message/run lifecycle. Replays the full multi-turn `messages` list (skipping the
    system message, since it's already baked into the agent's instructions) into one
    thread so retry/self-correction context (prior attempt + validation errors) is
    preserved. Defaults to the pre-created author agent (DEFAULT_AUTHOR_AGENT_ID)
    unless a different agent_id is supplied. Raises on any failure -- no fallback."""
    from azure.ai.agents import AgentsClient
    from azure.identity import DefaultAzureCredential

    active_agent_id = agent_id or DEFAULT_AUTHOR_AGENT_ID
    client = AgentsClient(endpoint=project_endpoint, credential=DefaultAzureCredential())

    thread = client.threads.create()
    for m in messages:
        if m["role"] in ("user", "assistant"):
            client.messages.create(thread_id=thread.id, role=m["role"], content=m["content"])
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


def _call_llm_chat(messages: list[dict], backend: str, ollama_host: str, ollama_model: str,
                    ai_foundry_endpoint: str | None, ai_foundry_model: str | None,
                    ai_foundry_agent_id: str | None) -> str:
    if backend == "ollama":
        return _call_ollama_chat(messages, ollama_host, ollama_model)
    if backend == "ai-foundry":
        if not ai_foundry_endpoint:
            raise RuntimeError(
                "backend='ai-foundry' requires ai_foundry_endpoint "
                "(--ai-foundry-endpoint or AI_FOUNDRY_PROJECT_ENDPOINT). ai_foundry_model is only "
                "needed if you're creating a brand-new agent -- the default persistent agent "
                "already has a model configured."
            )
        return _call_ai_foundry_chat(messages, ai_foundry_endpoint, ai_foundry_model, ai_foundry_agent_id)
    raise RuntimeError(f"Unknown LLM backend '{backend}'. Use 'ollama' or 'ai-foundry'.")


def generate_main_bicep_with_llm(
    user_prompt: str, resolution: ResolutionResult, requested_counts: dict[str, int],
    dest_root: Path, backend: str = "ollama",
    ollama_host: str = DEFAULT_OLLAMA_HOST, ollama_model: str = DEFAULT_OLLAMA_MODEL,
    ai_foundry_endpoint: str | None = None, ai_foundry_model: str | None = None,
    ai_foundry_agent_id: str | None = None,
    max_attempts: int = 2,
) -> tuple[str | None, list[str], bool]:
    """Generates main.bicep by asking the LLM to author it, validating with
    `az bicep build` after every attempt, and feeding validation errors back
    for self-correction. Requires dest_root/modules to already be populated
    (copy_modules must run first) so validation can actually resolve module
    references. Returns (bicep_text_or_None, log, success)."""
    log: list[str] = []
    main_path = dest_root / "main.bicep"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_generation_prompt(user_prompt, resolution, requested_counts)},
    ]

    for attempt in range(1, max_attempts + 1):
        log.append(f"LLM main.bicep generation attempt {attempt}/{max_attempts} (backend={backend})...")
        raw = _call_llm_chat(messages, backend, ollama_host, ollama_model,
                              ai_foundry_endpoint, ai_foundry_model, ai_foundry_agent_id)
        code = _extract_bicep(raw)
        main_path.write_text(code, encoding="utf-8")

        ok, output = validate_with_az(main_path)
        if ok:
            log.append(f"LLM-generated main.bicep validated successfully on attempt {attempt}.")
            return code, log, True

        log.append(f"Attempt {attempt} failed az bicep build validation.")
        messages.append({"role": "assistant", "content": raw})
        messages.append({
            "role": "user",
            "content": (
                f"That main.bicep failed `az bicep build` with these errors:\n{output}\n\n"
                f"Fix the errors and return the complete, corrected main.bicep file (full content, "
                f"not a diff)."
            ),
        })

    log.append(f"LLM could not produce a validating main.bicep after {max_attempts} attempts.")
    return None, log, False
