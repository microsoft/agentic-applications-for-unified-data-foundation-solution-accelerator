"""
CLI entry point for the infra composer agent.

The module SOURCE is fixed by default: the AVM Bicep module library that
lives in this repo on the `infra-core-modules-copy` branch, under
`infra_new/avm/modules`. It is cloned fresh (read-only, shallow) every run
so the agent always works from a clean, known copy regardless of where it
is invoked from.

The TARGET is dynamic: pass any repository URL via --target-repo. Each run
clones that repo fresh, creates a brand-new branch off its base branch
(default `main`), generates the composed Bicep project under an `infra-agents/`
subfolder of that checkout (configurable via --dest-name; pass '.' to write
at the repo root instead), commits, and pushes -- so the same command can be
pointed at a different repo (or the same repo again) every time with
different results, driven entirely by --prompt and --target-repo.

Usage (typical, fully automatic -- clones both repos, branches, generates,
validates, commits, and pushes to the target repo):
    python agent.py \
        --prompt "2 storage accounts and 1 app service" \
        --target-repo https://github.com/<org>/<some-target-repo>.git

Local-only dry run (generates into a local folder, no cloning/git at all):
    python agent.py --prompt "..." --no-git --dest-name ./out
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import git_ops
import github_app_auth
import env_file
from module_index import build_index, ModuleInfo
from resolver import resolve
from composer import copy_modules
from llm_interpreter import interpret_with_llm
from llm_composer import generate_main_bicep_with_llm, fix_bicep_with_llm
from bicep_validate import validate_with_az
import interactive
import readme_gen
import bicepparam_gen
import tech_patterns

# Fixed source: the module library this agent always composes from.
#
# Primary mode (default): a LOCAL directory on disk -- 001-wip-repo-structure/
# stable-cores/ -- that holds one subfolder per "stable core" project
# (currently agentic-apps/, with ms-iq/ reserved for more Bicep modules to be
# added there later). Every project's own <project>/infra/bicep/modules/
# folder is scanned automatically (see module_index.build_index, which
# rglobs every *.bicep file under whatever root it's given), so adding a new
# stable core -- or populating ms-iq/infra/bicep/modules once it exists --
# is picked up on the next run with no code change here.
#
# Fallback mode: the original clone-a-branch-of-this-repo flow (--source-repo/
# --source-branch/--source-path), still available via --source-local-path ''
# (or a path that doesn't exist) for whoever still wants to point at a
# different repo/branch entirely.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_LOCAL_PATH = REPO_ROOT / "001-wip-repo-structure" / "stable-cores"

DEFAULT_SOURCE_REPO = "https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator.git"
DEFAULT_SOURCE_BRANCH = "infra-core-modules-copy"
DEFAULT_SOURCE_PATH = "infra_new/avm/modules"


def _interpret_requests(text: str, modules: list[ModuleInfo],
                         ai_foundry_endpoint: str | None, ai_foundry_model: str | None,
                         ai_foundry_interpreter_agent_id: str | None, log: list[str],
                         baseline: list[tuple[str, str]] | None = None):
    """Interprets free text into ResourceRequest objects (to add) plus a list
    of raw exclude strings (baseline items to drop/replace, only meaningful
    when `baseline` is given) via the persistent Azure AI Foundry interpreter
    agent -- the only interpretation backend. Factored out so the
    interactive 'add more resources' loop in compose() can reuse it verbatim
    on whatever free text the user adds afterwards."""
    endpoint = ai_foundry_endpoint or os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
    foundry_model = ai_foundry_model or os.environ.get("AI_FOUNDRY_MODEL_DEPLOYMENT")
    interpreter_agent_id = ai_foundry_interpreter_agent_id or os.environ.get("AI_FOUNDRY_INTERPRETER_AGENT_ID")
    return interpret_with_llm(
        text, modules,
        project_endpoint=endpoint, model_deployment=foundry_model, agent_id=interpreter_agent_id,
        baseline=baseline,
    )


def _print_essential_log(log: list[str]) -> None:
    """Prints only the log lines that matter for troubleshooting or final
    confirmation -- warnings/errors, and the main.bicep generation outcome.
    Routine bookkeeping (module counts, matched-resource detail, exclude/
    plan detail) is intentionally NOT re-printed here since it's already
    shown live during the interactive steps in interactive.py -- this avoids
    dumping the same information twice and keeps the console output focused
    on what actually needs attention."""
    keep_markers = ("WARNING", "Generated ", "validated successfully", "failed az bicep build")
    for line in log:
        if any(line.startswith(m) or m in line for m in keep_markers):
            print(line)


def _match_excludes(excludes: list[str], candidates: list, modules_by_key: dict | None = None) -> list:
    """Fuzzy-matches each raw exclude string (e.g. 'Cosmos DB') against a
    small candidate list -- either ResourceEntry objects (pattern baseline)
    or ModuleInfo objects (already-resolved modules) -- restricted to just
    these candidates so an exclude phrase can never accidentally remove
    something unrelated from the wider catalog.

    When `modules_by_key` is given, each ResourceEntry candidate is first
    resolved to its REAL ModuleInfo (via _resolve_pattern_module) and scored
    with the same tag-based score_module() used for every other match in
    this codebase -- this matters because tag-based Jaccard similarity
    correctly disambiguates near-duplicate names (e.g. 'App Service' matches
    compute/app-service.bicep, not compute/app-service-plan.bicep, since the
    Plan module's tag set includes extra 'plan'/'serverfarm' tags that lower
    its similarity score). Falls back to raw display_name/module_key text
    scoring only when a ResourceEntry can't be resolved to a real module
    (already-warned-missing case) or modules_by_key wasn't supplied."""
    from request_parser import _tokenize, score_module

    matched = []
    for phrase in excludes:
        tokens = _tokenize(phrase)
        if not tokens:
            continue
        best_score = 0.0
        best_candidate = None
        for c in candidates:
            resolved_module = c if hasattr(c, "tags") else None
            if resolved_module is None and modules_by_key is not None:
                resolved_module = _resolve_pattern_module(c.module_key, modules_by_key)
            if resolved_module is not None:
                s = score_module(tokens, resolved_module)
            else:
                # ResourceEntry with no real module to resolve against: fall
                # back to scoring its own display_name/module_key text directly.
                name_tokens = set(_tokenize(f"{c.display_name} {c.module_key}"))
                token_set = set(tokens)
                s = len(token_set & name_tokens) / len(token_set | name_tokens) if (token_set | name_tokens) else 0.0
            if s > best_score:
                best_score = s
                best_candidate = c
        if best_candidate is not None and best_score > 0:
            matched.append(best_candidate)
    return matched



def _resolve_pattern_module(module_key: str, modules_by_key: dict) -> "ModuleInfo | None":
    """Resolves a technical pattern's ResourceEntry.module_key (a short,
    category-relative key like 'compute/app-service-plan.bicep', the format
    baked into tech_patterns.py's catalog/READMEs) against the REAL module
    index, whose ModuleInfo.key is now the full path under the scanned
    source root (e.g. 'agentic-apps/infra/bicep/modules/compute/app-service-plan.bicep'
    since the stable-cores multi-project layout was adopted -- see
    module_index.py's _derive_category). An exact key match is tried first
    (covers any source layout that still uses short keys directly), then
    falls back to matching any indexed module whose key ENDS WITH the short
    key on a path-segment boundary, so pattern baselines keep working
    regardless of which project prefix currently provides that module."""
    exact = modules_by_key.get(module_key)
    if exact is not None:
        return exact
    suffix = "/" + module_key
    matches = [m for m in modules_by_key.values() if m.key == module_key or m.key.endswith(suffix)]
    if not matches:
        return None
    # Deterministic tie-break when more than one project provides a module
    # with the same short key: prefer the shortest full path (fewest nested
    # project segments), then alphabetical, so re-runs are stable.
    matches.sort(key=lambda m: (len(m.key), m.key))
    return matches[0]


def compose(prompt: str, source_root: Path, dest_root: Path,
            ai_foundry_endpoint: str | None = None, ai_foundry_model: str | None = None,
            ai_foundry_interpreter_agent_id: str | None = None,
            ai_foundry_author_agent_id: str | None = None,
            non_interactive: bool = False, readme_pattern: str = "ask",
            tech_pattern: str | None = None, skip_prompt_interpretation: bool = False) -> tuple[Path, list[str]]:
    """Runs the full pipeline. Returns (main_bicep_path, human_readable_log).

    skip_prompt_interpretation: set True when `prompt` is only a synthetic
    label (e.g. "<pattern> solution", auto-filled when the user relied purely
    on a technical pattern and typed no resource description of their own) --
    prevents that label's own words (like the pattern name) from being
    re-interpreted as an extra resource request and double-counting
    something the pattern already added."""
    log: list[str] = []

    modules = build_index(source_root)
    log.append(f"Indexed {len(modules)} modules under {source_root}")
    modules_by_key = {m.key: m for m in modules}

    # Technical-pattern workflow: match the user's prompt to a predefined
    # pattern (chat-with-data, document-processing, call-center,
    # realtime-alerts -- see tech_patterns.py), READ that pattern's own
    # README.md (the on-disk file is the real source of truth -- hand edits
    # to it are picked up automatically), and show the exact resource list
    # it declares. Nothing is pulled from the source module library and no
    # module is selected until the user explicitly confirms this plan.
    #
    # The pattern choice and the resulting resource plan are confirmed
    # TOGETHER in one round-trip (interactive.confirm_pattern_plan) instead
    # of two separate prompts -- if the user declines, they pick a different
    # pattern (or none) and this loop recomputes the plan for that choice.
    chosen_tech_pattern = interactive.choose_tech_pattern(prompt, tech_pattern, non_interactive, log)

    selected: list[ModuleInfo] = []
    requested_counts: dict[str, int] = {}
    pattern_resources: list = []
    adjusted_pattern_resources: list = []
    source_desc = ""
    requests: list = []
    excludes: list = []

    for _ in range(3):
        pattern_resources, source_desc = ([], "")
        if chosen_tech_pattern:
            pattern_resources, source_desc = tech_patterns.get_pattern_resources(chosen_tech_pattern)
            log.append(f"Read {len(pattern_resources)} resource(s) for pattern '{chosen_tech_pattern}' from {source_desc}.")

        # Interpret the user's own --prompt text -- whether or not a pattern
        # is in play. When a pattern IS in play, the pattern's own resource
        # list is passed as `baseline` so the interpreter can also report
        # `excludes`: baseline items the prompt explicitly said not to use
        # (or to replace with something else), e.g. "follow document
        # processing but no event grid and use postgres instead of cosmos"
        # -> excludes=["Event Grid","Cosmos DB (NoSQL)"], resources=[postgres].
        # This means the pattern's baseline table is only ever a STARTING
        # POINT that the user's own words can trim/substitute -- never
        # blindly applied in full regardless of what the prompt actually
        # asked for. Re-run every time the pattern changes (loop iteration)
        # so `excludes` are matched against the right baseline.
        if skip_prompt_interpretation:
            log.append("Skipping prompt interpretation: no resource description was provided beyond the "
                        "technical pattern (nothing to add or exclude).")
            requests, excludes = [], []
        else:
            log.append("Interpreting prompt via the persistent AI Foundry agent "
                       "'infra-composer-prompt-interpreter'...")
            baseline_pairs = [(r.display_name, r.module_key) for r in pattern_resources] or None
            requests, excludes = _interpret_requests(
                prompt, modules,
                ai_foundry_endpoint, ai_foundry_model, ai_foundry_interpreter_agent_id, log,
                baseline=baseline_pairs,
            )
            log.append(f"LLM identified {len(requests)} resource concept(s) to add"
                       + (f" and {len(excludes)} baseline item(s) to exclude/replace" if pattern_resources else "")
                       + " from the prompt.")

        if not chosen_tech_pattern:
            adjusted_pattern_resources = []
            break

        excluded_entries = _match_excludes(excludes, pattern_resources, modules_by_key) if excludes else []
        if excluded_entries:
            for e in excluded_entries:
                log.append(f"Excluding pattern resource '{e.display_name}' ({e.module_key}) -- your prompt "
                           f"asked to drop or replace it.")
        adjusted_pattern_resources = [r for r in pattern_resources if r not in excluded_entries]

        decision = interactive.confirm_pattern_plan(
            chosen_tech_pattern, adjusted_pattern_resources, source_desc, non_interactive, log,
            excluded=excluded_entries,
        )
        if decision == "yes":
            break
        if decision == "none":
            chosen_tech_pattern = None
            continue
        # decision is a different catalog pattern id -- recompute the plan for it.
        chosen_tech_pattern = decision
    else:
        raise SystemExit(
            "Could not agree on a resource plan after multiple attempts. Re-run with a different "
            "--prompt/--tech-pattern."
        )

    if chosen_tech_pattern:
        for r in adjusted_pattern_resources:
            module = _resolve_pattern_module(r.module_key, modules_by_key)
            if module is None:
                log.append(
                    f"WARNING: pattern resource '{r.display_name}' references module '{r.module_key}' "
                    f"which was not found in the source library (skipped)."
                )
                continue
            selected.append(module)
            requested_counts[module.key] = requested_counts.get(module.key, 0) + 1

    for req in requests:
        if req.matched_module is None:
            log.append(f"WARNING: could not match request '{req.text.strip()}' to any module (skipped)")
            continue
        log.append(
            f"Matched '{req.text.strip()}' -> {req.matched_module.key} "
            f"(score={req.score:.2f}, count={req.count})"
        )
        if req.matched_module not in selected:
            selected.append(req.matched_module)
        requested_counts[req.matched_module.key] = requested_counts.get(req.matched_module.key, 0) + req.count

    if not selected:
        raise SystemExit("No resources could be matched from the prompt or technical pattern. Aborting.")

    resolution = resolve(selected, modules)
    for key in resolution.modules:
        if key not in resolution.explicitly_requested:
            log.append(f"Auto-included dependency: {key}")
    for mod_key, pname in resolution.unresolved:
        log.append(f"WARNING: {mod_key} requires '{pname}' but no matching module/output was found; surfaced as a param")

    # Interactive resource-confirmation loop: show what's resolved so far and
    # let the user add more (in plain text) before anything is copied or
    # generated. Bounded to avoid an accidental infinite loop from repeated
    # blank confirmations in a scripted/piped stdin scenario.
    for _ in range(5):
        addition_text = interactive.confirm_resources(resolution, requested_counts, non_interactive, log)
        if not addition_text:
            break
        baseline_pairs = [(m.name, m.key) for m in selected] or None
        extra_requests, extra_excludes = _interpret_requests(
            addition_text, modules,
            ai_foundry_endpoint, ai_foundry_model, ai_foundry_interpreter_agent_id, log,
            baseline=baseline_pairs,
        )
        if extra_excludes:
            removed = _match_excludes(extra_excludes, selected)
            for m in removed:
                selected.remove(m)
                requested_counts.pop(m.key, None)
                log.append(f"Removed '{m.name}' ({m.key}) -- you asked to drop or replace it.")
        for req in extra_requests:
            if req.matched_module is None:
                log.append(f"WARNING: could not match added request '{req.text.strip()}' to any module (skipped)")
                continue
            log.append(f"Matched added request '{req.text.strip()}' -> {req.matched_module.key} (score={req.score:.2f}, count={req.count})")
            if req.matched_module not in selected:
                selected.append(req.matched_module)
            existing_count = requested_counts.get(req.matched_module.key, 0)
            requested_counts[req.matched_module.key] = existing_count + req.count
        resolution = resolve(selected, modules)
        for key in resolution.modules:
            if key not in resolution.explicitly_requested:
                log.append(f"Auto-included dependency: {key}")

    # Interactive unresolved-parameter resolution: ask whether to hardcode a
    # value for anything resolver.py couldn't wire up automatically, instead
    # of always silently surfacing it as a bare top-level parameter. These
    # user-supplied literals are threaded into the LLM's main.bicep authoring
    # prompt below (build_generation_prompt) so they still take effect even
    # though there is no deterministic template consuming them directly.
    param_defaults = interactive.resolve_unresolved_params(resolution, non_interactive, log)

    # NOTE: dest_root may be the target repo's own root (when --dest-name is
    # "."), which also contains .git -- never rmtree the whole directory.
    # Only clear the specific outputs this agent owns (modules/, main.bicep,
    # README.md) so re-running against the same target is idempotent without
    # touching unrelated files already in the repo.
    dest_root.mkdir(parents=True, exist_ok=True)
    modules_dir = dest_root / "modules"
    if modules_dir.exists():
        shutil.rmtree(modules_dir)

    copy_modules(resolution, source_root, dest_root)
    log.append(f"Copied {len(resolution.modules)} module files into {dest_root / 'modules'}")

    main_path = dest_root / "main.bicep"
    log.append("Generating main.bicep with the LLM (architect-style: feature flags, conditionals, "
                "wired outputs)...")
    endpoint = ai_foundry_endpoint or os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
    foundry_model = ai_foundry_model or os.environ.get("AI_FOUNDRY_MODEL_DEPLOYMENT")
    author_agent_id = ai_foundry_author_agent_id or os.environ.get("AI_FOUNDRY_AUTHOR_AGENT_ID")
    llm_code, gen_log, ok = generate_main_bicep_with_llm(
        prompt, resolution, requested_counts, dest_root, param_defaults,
        ai_foundry_endpoint=endpoint, ai_foundry_model=foundry_model, ai_foundry_agent_id=author_agent_id,
    )
    log.extend(gen_log)
    if not ok:
        log.append("The main.bicep author agent's own self-correction retries were exhausted; making "
                    "one more repair attempt with the dedicated fixer pass before giving up.")
        _, last_errors = validate_with_az(main_path)
        _, fix_log, fixed = fix_bicep_with_llm(
            main_path, last_errors,
            ai_foundry_endpoint=endpoint, ai_foundry_model=foundry_model,
            ai_foundry_agent_id=author_agent_id, source_label="LLM-authored main.bicep",
        )
        log.extend(fix_log)
        if not fixed:
            # compose() is about to raise, which means main() never gets a
            # chance to print this log via _print_essential_log() -- print
            # it here first so the real `az bicep build` errors (captured in
            # gen_log/fix_log above) are actually visible instead of just
            # the generic message below.
            _print_essential_log(log)
            raise SystemExit(
                f"The AI Foundry author agent could not produce a main.bicep that passes `az bicep build` "
                f"after all retries and the dedicated repair pass. There is no deterministic fallback -- "
                f"see the errors printed above, then either adjust the prompt/resource "
                f"list and re-run, or fix {main_path} by hand."
            )
    log.append(f"Generated {main_path}")

    bicepparam_path = bicepparam_gen.generate_bicepparam(main_path, dest_root)
    if bicepparam_path:
        log.append(f"Generated {bicepparam_path} (placeholder values for every required top-level "
                   f"parameter -- edit before deploying, or override with `az deployment group create "
                   f"--parameters {bicepparam_path.name}`).")
    else:
        log.append("No required top-level parameters without defaults -- skipping main.bicepparam "
                   "(nothing to scaffold).")

    chosen_pattern = interactive.choose_readme_pattern(prompt, readme_pattern, non_interactive, log)
    doc_paths = readme_gen.generate_docs(chosen_pattern, prompt, resolution, requested_counts, dest_root,
                                          tech_pattern=chosen_tech_pattern)
    for p in doc_paths:
        log.append(f"Generated {p}")

    return main_path, log


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].strip("-") or "infra"


def default_branch_name(tech_pattern: str | None) -> str:
    """Simple, unique branch name -- deliberately NOT derived from the full
    --prompt text (that produced long, awkward names full of arbitrary
    prompt words). Uses the resolved technical pattern id if one was
    chosen (e.g. 'document-processing'), else the generic 'custom', plus a
    timestamp and a short random suffix so re-runs never collide."""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    short_id = uuid.uuid4().hex[:6]
    label = tech_pattern or "custom"
    return f"infra/{label}-{stamp}-{short_id}"


def main() -> int:
    env_file.load_env_file()

    parser = argparse.ArgumentParser(
        description="Compose deployable Bicep infra from the fixed module library, "
                    "then branch/commit/push it into the ROOT of any target repo."
    )
    parser.add_argument("--prompt", required=False, default=None,
                         help="Natural-language infra request, e.g. '2 storage accounts and 1 app service'. "
                              "If omitted, the agent asks for it interactively at startup (unless "
                              "--non-interactive is set, in which case it is required).")

    parser.add_argument("--source-local-path", default=str(DEFAULT_SOURCE_LOCAL_PATH),
                         help="Local directory to scan for Bicep modules directly from disk, no git clone "
                              f"(default: {DEFAULT_SOURCE_LOCAL_PATH} -- the 'stable-cores' folder, which "
                              "holds one subfolder per project, e.g. agentic-apps/infra/bicep/modules, "
                              "ms-iq/infra/bicep/modules once populated. Every project's modules folder "
                              "under this path is discovered and indexed automatically -- no per-project "
                              "config needed here when a new one is added.). Pass '' (empty string) to "
                              "disable local-path mode and fall back to cloning --source-repo instead.")
    parser.add_argument("--source-repo", default=DEFAULT_SOURCE_REPO,
                         help=f"Fallback module library repo to clone when --source-local-path is '' or "
                              f"doesn't exist (fixed by default: {DEFAULT_SOURCE_REPO}).")
    parser.add_argument("--source-branch", default=DEFAULT_SOURCE_BRANCH,
                         help=f"Branch of the fallback module library repo (default: {DEFAULT_SOURCE_BRANCH}).")
    parser.add_argument("--source-path", default=DEFAULT_SOURCE_PATH,
                         help=f"Path within the fallback source repo to the modules root (default: {DEFAULT_SOURCE_PATH}).")

    parser.add_argument("--target-repo", required=False,
                         help="URL of the target repo to clone, branch, and push the generated project into. "
                              "Required unless --no-git is set.")
    parser.add_argument("--target-base", default="main", help="Base branch in the target repo to branch from (default: main).")
    parser.add_argument("--branch-name", default=None,
                         help="New branch name in the target repo. Auto-generated from the prompt + timestamp if omitted.")
    parser.add_argument("--dest-name", default="infra-agents",
                         help="Folder (relative to the target repo root) to write the composition into. "
                              "Default 'infra-agents' keeps the generated main.bicep/modules/README.md in "
                              "their own subfolder instead of the target repo root. Pass '.' to write "
                              "directly at the target repo root instead.")

    parser.add_argument("--ai-foundry-endpoint", default=None,
                         help="Azure AI Foundry project endpoint (required -- the agent always interprets "
                              "prompts and authors main.bicep via the persistent AI Foundry agents, with no "
                              "deterministic fallback). Falls back to AI_FOUNDRY_PROJECT_ENDPOINT env var.")
    parser.add_argument("--ai-foundry-model", default=None,
                         help="Model deployment name (only used if creating brand-new agents; the two "
                              "default persistent agents already have a model configured). "
                              "Falls back to AI_FOUNDRY_MODEL_DEPLOYMENT env var.")
    parser.add_argument("--ai-foundry-interpreter-agent-id", default=None,
                         help="Override the persistent AI Foundry agent used for prompt interpretation "
                              "(default: DEFAULT_INTERPRETER_AGENT_ID in llm_interpreter.py, the pre-created "
                              "'infra-composer-prompt-interpreter' agent). Falls back to "
                              "AI_FOUNDRY_INTERPRETER_AGENT_ID env var.")
    parser.add_argument("--ai-foundry-author-agent-id", default=None,
                         help="Override the persistent AI Foundry agent used to author main.bicep "
                              "(default: DEFAULT_AUTHOR_AGENT_ID in llm_composer.py, the pre-created "
                              "'infra-composer-main-bicep-author' agent). Falls back to "
                              "AI_FOUNDRY_AUTHOR_AGENT_ID env var.")
    parser.add_argument("--validate", action="store_true", help="Run 'az bicep build' on the generated main.bicep.")
    parser.add_argument("--non-interactive", "--yes", dest="non_interactive", action="store_true",
                         help="Skip every interactive prompt (README pattern choice, resource-confirmation, "
                              "unresolved-parameter follow-ups) and use safe defaults instead. Use this for "
                              "scripted/CI runs where no one is watching stdin.")
    parser.add_argument("--readme-pattern", default="ask", choices=["ask", "solution-accelerator", "sample"],
                         help="Which README/deployment-doc pattern to generate: 'solution-accelerator' "
                              "(README.md + docs/DeploymentGuide.md, modeled on "
                              "microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator), 'sample' "
                              "(single README.md with a Mermaid diagram, modeled on "
                              "Azure-Samples/chat-with-your-data-solution-accelerator), or 'ask' (default -- "
                              "prompt interactively, suggesting one based on the prompt text; falls back to "
                              "'solution-accelerator' under --non-interactive).")
    parser.add_argument("--tech-pattern", default=None,
                         choices=list(tech_patterns.PATTERNS) + ["none"],
                         help="Seed this composition from a predefined technical pattern (see "
                              "tech_patterns.py / 001-wip-repo-structure/technical-patterns/<id>/README.md): "
                              f"{', '.join(tech_patterns.PATTERNS)}. Its baseline resource list is prepended "
                              "to --prompt before interpretation, and you can still add/remove resources "
                              "interactively afterwards. Pass 'none' to disable pattern seeding entirely. "
                              "If omitted, the agent tries to infer a pattern from --prompt and (unless "
                              "--non-interactive) asks interactively before proceeding.")
    parser.add_argument("--no-git", action="store_true",
                         help="Skip cloning/branching/pushing entirely; just generate files locally under --dest-name.")
    parser.add_argument("--no-push", action="store_true",
                         help="Clone, branch, generate, and commit, but do not push to the remote.")
    parser.add_argument("--keep-clones", action="store_true",
                         help="Don't delete the temporary source/target clones after finishing (for inspection).")
    args = parser.parse_args()

    ai_foundry_endpoint = args.ai_foundry_endpoint or os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
    if not ai_foundry_endpoint:
        raise SystemExit(
            "--ai-foundry-endpoint (or AI_FOUNDRY_PROJECT_ENDPOINT env var) is required: this agent always "
            "interprets prompts and authors main.bicep via the persistent Azure AI Foundry agents -- there "
            "is no deterministic/local fallback backend."
        )

    # Keep the persistent agents' stored instructions in sync with the local
    # source (llm_interpreter.INTERPRETER_INSTRUCTIONS / llm_composer.SYSTEM_PROMPT)
    # on every run, so editing those files takes effect immediately without a
    # separate `update_agent_instructions.py` step. Silent on success (this
    # is routine bookkeeping, not something the user needs to see every run);
    # a sync failure (e.g. no Azure credentials / offline) is still surfaced
    # as a warning, since it's non-fatal but worth knowing about.
    try:
        import update_agent_instructions
        update_agent_instructions.sync_agent_instructions(ai_foundry_endpoint)
    except Exception as exc:
        print(f"WARNING: could not sync agent instructions, continuing with live agent as-is: {exc}")

    skip_prompt_interpretation = False
    if not args.prompt:
        if args.non_interactive:
            raise SystemExit("--prompt is required when --non-interactive is set (there is no one to ask).")
        prompt_text = input(
            "\nWhat would you like me to deploy? Describe it in your own words:\n> "
        ).strip()
        if not prompt_text:
            raise SystemExit("No description provided -- nothing to compose.")
        args.prompt = prompt_text
        # No forced pattern menu: choose_tech_pattern() infers a technical
        # pattern (if any) directly from this same free text later in
        # compose(), and any extra resources mentioned alongside a pattern
        # reference (e.g. "...but also add one more fabric resource") are
        # still interpreted normally since args.prompt carries the full text.


    # Resolve the technical pattern (if any) up front -- purely once, here --
    # to build a simple/unique branch name from its id. This is the ONLY
    # place choose_tech_pattern's inference/confirmation prompt runs when
    # --tech-pattern wasn't given explicitly; the resolved id is then passed
    # into compose() below as an already-decided value (never None -- "none"
    # means "confirmed no pattern") so compose() doesn't ask again.
    log: list[str] = []
    resolved_tech_pattern = interactive.choose_tech_pattern(args.prompt, args.tech_pattern, args.non_interactive, log)
    branch_name = args.branch_name or default_branch_name(resolved_tech_pattern)
    tech_pattern_for_compose = resolved_tech_pattern or "none"
    tmp_root = Path(tempfile.mkdtemp(prefix="infra-composer-"))
    source_clone_dir = tmp_root / "source"
    target_clone_dir = tmp_root / "target"

    local_source = Path(args.source_local_path).resolve() if args.source_local_path else None
    use_local_source = local_source is not None and local_source.is_dir()

    try:
        if use_local_source:
            print(f"Reading source module library directly from disk: {local_source} "
                  f"(no clone -- every project's infra/bicep/modules folder under this path is scanned).")
            source_root = local_source
        else:
            if args.source_local_path:
                print(f"Local source path '{args.source_local_path}' does not exist -- "
                      f"falling back to cloning {args.source_repo}@{args.source_branch}.")
            print(f"Cloning source module library ({args.source_repo} @ {args.source_branch})...")
            git_ops.clone_repo(args.source_repo, source_clone_dir, branch=args.source_branch)
            source_root = source_clone_dir / args.source_path

        if args.no_git:
            dest_root = tmp_root / "generated-infra" if args.dest_name == "." else Path(args.dest_name).resolve()
            main_path, compose_log = compose(args.prompt, source_root, dest_root,
                                      ai_foundry_endpoint=args.ai_foundry_endpoint,
                                      ai_foundry_model=args.ai_foundry_model,
                                      ai_foundry_interpreter_agent_id=args.ai_foundry_interpreter_agent_id,
                                      ai_foundry_author_agent_id=args.ai_foundry_author_agent_id,
                                      non_interactive=args.non_interactive, readme_pattern=args.readme_pattern,
                                      tech_pattern=tech_pattern_for_compose,
                                      skip_prompt_interpretation=skip_prompt_interpretation)
            log.extend(compose_log)
            _print_essential_log(log)
            print(f"Generated locally at {dest_root} (no git operations performed).")
            if args.validate:
                ok, output = validate_with_az(main_path)
                print("VALIDATION:", "PASSED" if ok else "FAILED")
                if not ok:
                    print(output)
                    return 1
            return 0

        if not args.target_repo:
            raise SystemExit("--target-repo is required unless --no-git is set.")

        target_repo_url = args.target_repo
        bot_name = bot_email = None
        if github_app_auth.is_configured():
            print("GitHub App credentials detected (GH_APP_ID/GH_APP_INSTALLATION_ID) -- "
                  "using an app installation token instead of the local git credential helper, "
                  "so commits/pushes are attributed to the app's own bot identity.")
            app_token = github_app_auth.get_installation_token()
            target_repo_url = github_app_auth.inject_token_into_url(args.target_repo, app_token)
            bot_name, bot_email = github_app_auth.get_app_bot_identity(token=app_token)

        print(f"Cloning target repo ({args.target_repo})...")
        git_ops.clone_repo(target_repo_url, target_clone_dir)

        print(f"Creating branch '{branch_name}' in the target repo, based strictly on origin/{args.target_base} "
              f"(no other branch's history included)...")
        git_ops.create_branch_from_base(target_clone_dir, args.target_base, branch_name)

        dest_root = target_clone_dir if args.dest_name == "." else target_clone_dir / args.dest_name
        main_path, compose_log = compose(args.prompt, source_root, dest_root,
                                  ai_foundry_endpoint=args.ai_foundry_endpoint,
                                  ai_foundry_model=args.ai_foundry_model,
                                  ai_foundry_interpreter_agent_id=args.ai_foundry_interpreter_agent_id,
                                  ai_foundry_author_agent_id=args.ai_foundry_author_agent_id,
                                  non_interactive=args.non_interactive, readme_pattern=args.readme_pattern,
                                  tech_pattern=tech_pattern_for_compose,
                                  skip_prompt_interpretation=skip_prompt_interpretation)
        log.extend(compose_log)
        _print_essential_log(log)

        if args.validate:
            ok, output = validate_with_az(main_path)
            print("VALIDATION:", "PASSED" if ok else "FAILED")
            if not ok:
                print(output)
                return 1

        source_desc = (
            f"local module library at {local_source}"
            if use_local_source
            else f"{args.source_repo}@{args.source_branch}:{args.source_path}"
        )
        message = (
            f"Add generated infra composition: {args.prompt}\n\n"
            f"Auto-generated by infra_composer_agent from the above natural-language request, "
            f"composed from {source_desc}.\n\n"
            f"Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
        )
        result = git_ops.commit_paths(target_clone_dir, [dest_root], message,
                                       author_name=bot_name, author_email=bot_email)
        print(f"Commit: {result}")

        if not args.no_push:
            push_result = git_ops.push_branch(target_clone_dir, branch_name)
            print(f"Pushed: {push_result}")
            print(f"Branch '{branch_name}' pushed to {args.target_repo}")
        else:
            print("Skipped push (--no-push).")

        return 0
    finally:
        if not args.keep_clones:
            shutil.rmtree(tmp_root, ignore_errors=True)
            print(f"Removed temporary clones under {tmp_root}")
        else:
            print(f"Kept temporary clones under {tmp_root}")


if __name__ == "__main__":
    sys.exit(main())
