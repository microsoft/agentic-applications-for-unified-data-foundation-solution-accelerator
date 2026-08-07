"""
LLM-based main.bicep generator.

Why this exists: real hand-authored orchestrators (see infra/bicep/main.bicep
in this repo) are rich: WAF feature flags (enableMonitoring/
enablePrivateNetworking/enableScalability/enableRedundancy), existing-vs-new
conditionals, tags merging via union(), enableTelemetry threaded through
every module, diagnostic settings wiring, deployer()-based tag metadata, and
modules named/conditioned to reflect real intent rather than a flat 1:1
dump. A flat/static template can't reason about any of that, so main.bicep
authoring is done entirely by the LLM -- there is no deterministic/static
generator and no fallback to one.

This module asks a PERSISTENT Azure AI Foundry agent (named
"infra-composer-main-bicep-author" -- see DEFAULT_AUTHOR_AGENT_ID) to
actually *author* the main.bicep body -- reasoning about the request the
way an infrastructure architect would -- while staying safe:
  * The LLM is given the REAL resolved modules (exact relative paths,
    exact required/optional params, exact outputs) parsed by module_index.py.
    It cannot invent a module path or a parameter name that doesn't exist,
    because it's instructed to only use what's in that list.
  * Every attempt is validated with `az bicep build` before being accepted.
    If validation fails, the error output is fed back to the model for a
    self-correction retry (up to `max_attempts` times).
  * If the LLM still cannot produce a file that validates after all
    attempts, the caller (agent.py) raises a clear error instead of
    shipping unvalidated output -- the project's core success criterion is
    that the output must always be deployable without manual edits, so
    there is no silent, lower-quality fallback path to fall back to.

With every call, a real thread is opened against the persistent author agent
(visible in the AI Foundry portal's Agents tab) and prior attempts/errors are
replayed into that thread for retries -- not a stateless chat completion.
"""
from __future__ import annotations

import re
from pathlib import Path

from module_index import ModuleInfo
from resolver import ResolutionResult
from bicep_validate import validate_with_az

# Persistent AI Foundry agent, created once in the project (proj-default) so every
# run reuses the same registered agent instead of creating/deleting a temp one.
# Visible in the AI Foundry portal's Agents tab as "infra-composer-main-bicep-author".
DEFAULT_AUTHOR_AGENT_ID = "asst_XTQ6h2DoCHJMorowBAg9gJZb"

SKILLS_DIR = Path(__file__).resolve().parent / "skills"
BICEP_AUTHORING_SKILL_PATH = SKILLS_DIR / "bicep-main-authoring.md"


def _load_skill(path: Path = BICEP_AUTHORING_SKILL_PATH) -> str:
    """Loads a markdown 'skill' document -- a rule set the LLM author agent
    must follow -- from disk. This is the single source of truth for
    main.bicep authoring conventions (distilled from this repo's real
    infra/bicep/main.bicep); edit the markdown file, not this function, to
    change the rules. Falls back to an empty string (with a clear inline
    marker) if the file is ever missing, so a run never silently loses the
    style guide without at least surfacing it in the generated prompt."""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return (
        "(WARNING: bicep-main-authoring skill file not found at "
        f"{path} -- no authoring rules were loaded for this run.)"
    )


STYLE_GUIDE = _load_skill()

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


def build_generation_prompt(user_prompt: str, resolution: ResolutionResult, requested_counts: dict[str, int],
                             param_defaults: dict[str, str] | None = None) -> str:
    catalog = _module_catalog_text(resolution)
    counts_text = "\n".join(f"- {k}: requested count = {v}" for k, v in requested_counts.items())
    overrides_text = ""
    if param_defaults:
        overrides_lines = "\n".join(f"- {k}: {v}" for k, v in param_defaults.items())
        overrides_text = (
            f"\nUser-supplied literal values for parameters that had no matching module/output "
            f"(key is '<module path>::<param name>', use the literal value verbatim for that exact "
            f"param on that exact module -- quote it if the param type is a string):\n{overrides_lines}\n"
        )
    return (
        f"User's infrastructure request:\n{user_prompt}\n\n"
        f"Resolved modules available to use (exact paths/params/outputs -- use only these, "
        f"and use ALL of them):\n{catalog}\n\n"
        f"Requested instance counts (create this many `module` blocks for these, numbering symbol "
        f"names 1..N and their `name` params, if count > 1):\n{counts_text}\n"
        f"{overrides_text}\n"
        f"For any REQUIRED module parameter that is not a resource reference wireable to another "
        f"module's output and has no user-supplied literal value above, declare it as a top-level "
        f"main.bicep parameter (never omit a required parameter or invent a value).\n\n"
        f"Write the complete main.bicep now."
    )


def _extract_bicep(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:bicep)?\s*\n(.*?)```", text, re.DOTALL)
    if fence:
        return fence.group(1).strip() + "\n"
    return text + ("\n" if not text.endswith("\n") else "")


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


def _call_llm_chat(messages: list[dict], ai_foundry_endpoint: str | None, ai_foundry_model: str | None,
                    ai_foundry_agent_id: str | None) -> str:
    if not ai_foundry_endpoint:
        raise RuntimeError(
            "main.bicep authoring requires --ai-foundry-endpoint (or AI_FOUNDRY_PROJECT_ENDPOINT). "
            "ai_foundry_model is only needed if you're creating a brand-new agent -- the "
            "default persistent agent already has a model configured."
        )
    return _call_ai_foundry_chat(messages, ai_foundry_endpoint, ai_foundry_model, ai_foundry_agent_id)


def generate_main_bicep_with_llm(
    user_prompt: str, resolution: ResolutionResult, requested_counts: dict[str, int],
    dest_root: Path, param_defaults: dict[str, str] | None = None,
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
        {"role": "user", "content": build_generation_prompt(user_prompt, resolution, requested_counts, param_defaults)},
    ]

    for attempt in range(1, max_attempts + 1):
        log.append(f"LLM main.bicep generation attempt {attempt}/{max_attempts}...")
        raw = _call_llm_chat(messages, ai_foundry_endpoint, ai_foundry_model, ai_foundry_agent_id)
        code = _extract_bicep(raw)
        main_path.write_text(code, encoding="utf-8")

        ok, output = validate_with_az(main_path)
        if ok:
            log.append(f"LLM-generated main.bicep validated successfully on attempt {attempt}.")
            return code, log, True

        log.append(f"Attempt {attempt} failed az bicep build validation:\n{output}")
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


def fix_bicep_with_llm(
    main_path: Path, validation_errors: str,
    ai_foundry_endpoint: str | None = None, ai_foundry_model: str | None = None,
    ai_foundry_agent_id: str | None = None,
    max_attempts: int = 2, source_label: str = "generated main.bicep",
) -> tuple[str | None, list[str], bool]:
    """Repair pass for a main.bicep that already failed `az bicep build` --
    used as a final attempt to patch the LLM-authored file when
    generate_main_bicep_with_llm's own internal self-correction retries are
    exhausted (e.g. too many outputs, a module's custom type name copied
    verbatim into an output type position). Sends the real file content +
    the real `az bicep build` errors to the persistent author agent and
    asks it to make the minimal fix needed, re-validating after each
    attempt exactly like generate_main_bicep_with_llm's self-correction loop.
    Mutates main_path in place on every attempt so validate_with_az always
    checks the latest candidate. Returns (bicep_text_or_None, log, success)."""
    log: list[str] = []
    current_code = main_path.read_text(encoding="utf-8")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Here is a {source_label} that failed `az bicep build`:\n\n"
            f"```bicep\n{current_code}\n```\n\n"
            f"Validation errors/warnings:\n{validation_errors}\n\n"
            "Fix ONLY what is necessary to make this build successfully with `az bicep build` -- "
            "preserve every existing module reference, parameter wiring, and output that is not the "
            "direct cause of an error (e.g. if there are too many outputs, consolidate/remove the "
            "least essential ones rather than inventing new structure; if an output/param type isn't a "
            "valid Bicep type, replace it with the correct primitive/object type or drop that output). "
            "Do not invent new modules or remove required functionality. Return the complete, "
            "corrected main.bicep file (full content, not a diff)."
        )},
    ]

    for attempt in range(1, max_attempts + 1):
        log.append(f"Fixer-agent repair attempt {attempt}/{max_attempts} for {source_label}...")
        raw = _call_llm_chat(messages, ai_foundry_endpoint, ai_foundry_model, ai_foundry_agent_id)
        code = _extract_bicep(raw)
        main_path.write_text(code, encoding="utf-8")

        ok, output = validate_with_az(main_path)
        if ok:
            log.append(f"Fixer agent produced a validating main.bicep on attempt {attempt}.")
            return code, log, True

        log.append(f"Fixer attempt {attempt} still failed az bicep build validation.")
        messages.append({"role": "assistant", "content": raw})
        messages.append({
            "role": "user",
            "content": (
                f"Still failing `az bicep build`:\n{output}\n\n"
                f"Fix the errors and return the complete, corrected main.bicep file (full content, "
                f"not a diff)."
            ),
        })

    log.append(f"Fixer agent could not repair main.bicep after {max_attempts} attempts; "
               f"leaving the last generated content as-is.")
    return None, log, False
