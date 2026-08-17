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

This module asks Azure AI Foundry -- through a genuinely registered Foundry
Agent named "infra-composer-main-bicep-author" (see
foundry_client.ensure_agent/call_agent, modeled on microsoft/CAIRA's
foundry-client.ts) -- to actually *author* the main.bicep body -- reasoning
about the request the way an infrastructure architect would -- while
staying safe:
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

Each run calls `ensure_agent(...)` once to (re)publish the
"infra-composer-main-bicep-author" agent's instructions from this module's
SYSTEM_PROMPT (so the registered agent always matches whatever
bicep-main-authoring.md currently says), then every turn (initial draft,
self-correction retries, and the dedicated fixer
pass) runs through `call_agent(...)`, genuinely bound to that agent -- no
thread/run lifecycle to manage, and no server-side state to keep in sync
across retries beyond the in-memory message history already kept here.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from resolver import ResolutionResult
from bicep_validate import validate_with_az
from foundry_client import call_agent, ensure_agent

# Display name of the real, registered Azure AI Foundry Agent this module
# calls through (see foundry_client.ensure_agent/call_agent) -- same name
# as the pre-existing DEFAULT_AUTHOR_AGENT_NAME constant this replaces, kept
# as-is (already registered/visible in the Foundry portal) even though it's
# now genuinely called by name instead of just published for portal-
# visibility. Every authoring/fixer turn now genuinely runs AS this agent.
AUTHOR_AGENT_NAME = "infra-composer-main-bicep-author"

SKILLS_DIR = Path(__file__).resolve().parent / "skills"
BICEP_AUTHORING_SKILL_PATH = SKILLS_DIR / "bicep-main-authoring.md"

# Default self-correction retry budget for both the initial generation loop
# and the dedicated fixer pass. Overridable per-run via
# generate_main_bicep_with_llm/fix_bicep_with_llm's own `max_attempts` param
# (wired to --max-attempts / INFRA_COMPOSER_MAX_ATTEMPTS in agent.py), or
# globally by exporting INFRA_COMPOSER_MAX_ATTEMPTS before either function's
# own default kicks in.
DEFAULT_MAX_ATTEMPTS = int(os.environ.get("INFRA_COMPOSER_MAX_ATTEMPTS", "3"))


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_FRONTMATTER_VERSION_RE = re.compile(r'^\s*version:\s*["\']?([^"\'\n]+)["\']?\s*$', re.MULTILINE)


def _strip_frontmatter(text: str) -> str:
    """Strips a leading YAML frontmatter block (--- ... ---), if present,
    from a skill markdown file's content. Skill files carry frontmatter
    (name/description/compatibility/metadata) purely for external
    discoverability/portability -- e.g. so the file is self-describing the
    same way microsoft/CAIRA's SKILL.md files are -- but that metadata is
    not useful instruction content for the LLM prompt itself, so it's
    removed here rather than sent verbatim as part of the system prompt."""
    return _FRONTMATTER_RE.sub("", text, count=1).strip()


def _extract_frontmatter_version(text: str) -> str | None:
    """Pulls the `version:` field out of a skill file's YAML frontmatter
    block, if present, so a run's log can record exactly which revision of
    the authoring rules was in effect -- useful when comparing generated
    output across runs after the skill file itself has been edited. Returns
    None if there's no frontmatter or no version field (never raises)."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None
    version_match = _FRONTMATTER_VERSION_RE.search(match.group(1))
    return version_match.group(1).strip() if version_match else None


def _load_skill(path: Path = BICEP_AUTHORING_SKILL_PATH) -> tuple[str, str | None]:
    """Loads a markdown 'skill' document -- a rule set the LLM author agent
    must follow -- from disk. This is the single source of truth for
    main.bicep authoring conventions (distilled from this repo's real
    infra/bicep/main.bicep); edit the markdown file, not this function, to
    change the rules. Falls back to an empty string (with a clear inline
    marker) if the file is ever missing, so a run never silently loses the
    style guide without at least surfacing it in the generated prompt.
    Returns (stripped_content, frontmatter_version_or_None) so callers can
    log which skill revision was actually used for a given run."""
    if path.exists():
        raw = path.read_text(encoding="utf-8")
        return _strip_frontmatter(raw), _extract_frontmatter_version(raw)
    return (
        "(WARNING: bicep-main-authoring skill file not found at "
        f"{path} -- no authoring rules were loaded for this run.)",
        None,
    )


STYLE_GUIDE, SKILL_VERSION = _load_skill()

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
        rel = f"./modules/{module.flat_rel_path.as_posix()}"
        requested = " [EXPLICITLY REQUESTED BY USER]" if key in resolution.explicitly_requested else " [auto-included dependency]"
        lines.append(f"- Module path: {rel}{requested}")
        lines.append("  Params:")
        for p in module.params:
            lines.append(_format_param(p))
        lines.append(f"  Outputs: {', '.join(o.name for o in module.outputs) or '(none)'}")
    return "\n".join(lines)


def build_generation_prompt(user_prompt: str, resolution: ResolutionResult, requested_counts: dict[str, int],
                             param_defaults: dict[str, str] | None = None,
                             existing_resource_notes: list[str] | None = None) -> str:
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
    existing_resources_text = ""
    if existing_resource_notes:
        notes_lines = "\n".join(f"- {n}" for n in existing_resource_notes)
        existing_resources_text = (
            f"\nThe user wants to REUSE these existing resources instead of provisioning new ones for "
            f"the matching concept -- wire the literal value(s) below into the relevant module's "
            f"'existing<Thing>ResourceId' (or equivalent existing-resource) parameter, following this "
            f"repo's existing-vs-new pattern, rather than creating a new resource for that concept:\n"
            f"{notes_lines}\n"
        )
    return (
        f"User's infrastructure request:\n{user_prompt}\n\n"
        f"Resolved modules available to use (exact paths/params/outputs -- use only these, "
        f"and use ALL of them):\n{catalog}\n\n"
        f"Requested instance counts (create this many `module` blocks for these, numbering symbol "
        f"names 1..N and their `name` params, if count > 1):\n{counts_text}\n"
        f"{overrides_text}"
        f"{existing_resources_text}\n"
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


def _call_llm_chat(messages: list[dict], ai_foundry_endpoint: str | None, ai_foundry_model: str | None,
                    ai_foundry_agent_id: str | None = None) -> str:
    """Runs one turn AS the registered "infra-composer-main-bicep-author"
    Foundry Agent (foundry_client.call_agent) -- replaces the old
    thread/run-based _call_ai_foundry_chat, and before that, the raw unbound
    call_responses path. `ai_foundry_agent_id` is accepted for backward-compat
    CLI/env wiring but unused: the agent is now addressed by its fixed display
    name (AUTHOR_AGENT_NAME), not by a caller-supplied id. Publishes/refreshes
    the agent's instructions from SYSTEM_PROMPT once per process (see
    ensure_agent) before every call, so the registered agent always matches
    whatever bicep-main-authoring.md currently says on disk."""
    if not ai_foundry_endpoint:
        raise RuntimeError(
            "main.bicep authoring requires --ai-foundry-endpoint (or AI_FOUNDRY_PROJECT_ENDPOINT)."
        )
    ensure_agent(ai_foundry_endpoint, AUTHOR_AGENT_NAME, ai_foundry_model, SYSTEM_PROMPT)
    return call_agent(messages, ai_foundry_endpoint, AUTHOR_AGENT_NAME)


def _run_retry_loop(
    messages: list[dict], main_path: Path,
    ai_foundry_endpoint: str | None, ai_foundry_model: str | None, ai_foundry_agent_id: str | None,
    max_attempts: int, attempt_label: str, success_label: str, failure_feedback: str,
) -> tuple[str | None, list[str], bool]:
    """Shared self-correction retry loop used by BOTH generate_main_bicep_with_llm
    (first-draft authoring) and fix_bicep_with_llm (repair pass) -- the two
    previously had near-identical, independently-maintained copies of this
    exact loop (call LLM -> write file -> validate -> on failure, append
    assistant+feedback messages and retry). Consolidated here so there's one
    place to fix bugs or change retry behavior. `messages` must already
    contain the system + initial user turn; this function only appends
    attempt/feedback turns as it retries. Mutates main_path in place on
    every attempt so validate_with_az always checks the latest candidate.
    Returns (bicep_text_or_None, log, success)."""
    log: list[str] = []
    for attempt in range(1, max_attempts + 1):
        log.append(f"{attempt_label} attempt {attempt}/{max_attempts}...")
        raw = _call_llm_chat(messages, ai_foundry_endpoint, ai_foundry_model, ai_foundry_agent_id)
        code = _extract_bicep(raw)
        main_path.write_text(code, encoding="utf-8")

        ok, output = validate_with_az(main_path)
        if ok:
            log.append(f"{success_label} on attempt {attempt}.")
            return code, log, True

        log.append(f"Attempt {attempt} failed az bicep build validation:\n{output}")
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": failure_feedback.format(output=output)})

    log.append(f"{attempt_label} could not produce a validating main.bicep after {max_attempts} attempts.")
    return None, log, False


def generate_main_bicep_with_llm(
    user_prompt: str, resolution: ResolutionResult, requested_counts: dict[str, int],
    dest_root: Path, param_defaults: dict[str, str] | None = None,
    existing_resource_notes: list[str] | None = None,
    ai_foundry_endpoint: str | None = None, ai_foundry_model: str | None = None,
    ai_foundry_agent_id: str | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> tuple[str | None, list[str], bool]:
    """Generates main.bicep by asking the LLM to author it, validating with
    `az bicep build` after every attempt, and feeding validation errors back
    for self-correction. Requires dest_root/modules to already be populated
    (copy_modules must run first) so validation can actually resolve module
    references. Validation is strict (see bicep_validate.validate_with_az):
    genuine Bicep linter warnings (unused params, etc.) count as failures
    too, not just hard compile errors, so a run only ever "succeeds" with a
    main.bicep that has no issues at all. `max_attempts` defaults to
    DEFAULT_MAX_ATTEMPTS (overridable via INFRA_COMPOSER_MAX_ATTEMPTS env
    var, or --max-attempts in agent.py). Returns (bicep_text_or_None, log, success)."""
    main_path = dest_root / "main.bicep"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_generation_prompt(
            user_prompt, resolution, requested_counts, param_defaults, existing_resource_notes,
        )},
    ]
    return _run_retry_loop(
        messages, main_path, ai_foundry_endpoint, ai_foundry_model, ai_foundry_agent_id, max_attempts,
        attempt_label="LLM main.bicep generation",
        success_label="LLM-generated main.bicep validated successfully",
        failure_feedback=(
            "That main.bicep failed `az bicep build` with these errors:\n{output}\n\n"
            "Fix the errors and return the complete, corrected main.bicep file (full content, not a diff)."
        ),
    )


def fix_bicep_with_llm(
    main_path: Path, validation_errors: str,
    ai_foundry_endpoint: str | None = None, ai_foundry_model: str | None = None,
    ai_foundry_agent_id: str | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS, source_label: str = "generated main.bicep",
) -> tuple[str | None, list[str], bool]:
    """Repair pass for a main.bicep that already failed `az bicep build` --
    used as a final attempt to patch the LLM-authored file when
    generate_main_bicep_with_llm's own internal self-correction retries are
    exhausted (e.g. too many outputs, a module's custom type name copied
    verbatim into an output type position). Sends the real file content +
    the real `az bicep build` errors to the persistent author agent and
    asks it to make the minimal fix needed, re-validating after each
    attempt via the same shared _run_retry_loop used by
    generate_main_bicep_with_llm. Returns (bicep_text_or_None, log, success)."""
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
    return _run_retry_loop(
        messages, main_path, ai_foundry_endpoint, ai_foundry_model, ai_foundry_agent_id, max_attempts,
        attempt_label=f"Fixer-agent repair for {source_label}",
        success_label="Fixer agent produced a validating main.bicep",
        failure_feedback=(
            "Still failing `az bicep build`:\n{output}\n\n"
            "Fix the errors and return the complete, corrected main.bicep file (full content, not a diff)."
        ),
    )
