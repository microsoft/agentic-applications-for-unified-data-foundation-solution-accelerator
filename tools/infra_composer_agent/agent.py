"""
CLI entry point for the infra composer agent.

The module SOURCE is fixed by default: the AVM Bicep module library that
lives in this repo on the `infra-core-modules-copy` branch, under
`infra_new/avm/modules`. It is cloned fresh (read-only, shallow) every run
so the agent always works from a clean, known copy regardless of where it
is invoked from.

The TARGET is dynamic: pass any repository URL via --target-repo. Each run
clones that repo fresh, creates a brand-new branch off its base branch
(default `main`), generates the composed Bicep project under an
`infra-agents/bicep/` subfolder of that checkout (configurable via
--dest-name; pass '.' to write at the repo root instead), commits, and
pushes -- so the same command can be pointed at a different repo (or the
same repo again) every time with different results, driven entirely by
--prompt and --target-repo.

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
from conversational_planner import plan_resources_conversationally
from llm_composer import generate_main_bicep_with_llm, fix_bicep_with_llm
import plan_doc
import llm_composer
from bicep_validate import validate_with_az
import interactive
import readme_gen
import bicepparam_gen

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


def _check_az_bicep_available() -> None:
    """Fails fast, before any LLM calls are made, if the Azure CLI (with the
    'bicep' component) isn't available. Every main.bicep authoring attempt
    is gated on `az bicep build` (see bicep_validate.validate_with_az), so
    discovering a missing/broken `az` only after burning an LLM call deep
    inside the retry loop wastes both time and (metered) model usage for a
    problem that's entirely local-environment, not prompt/model related."""
    az_cmd = shutil.which("az") or shutil.which("az.cmd")
    if not az_cmd:
        raise SystemExit(
            "Azure CLI ('az') was not found on PATH. This agent requires `az bicep build` to validate "
            "every generated main.bicep -- install the Azure CLI (and run 'az bicep install' if needed) "
            "before running this command. See https://learn.microsoft.com/cli/azure/install-azure-cli."
        )
    proc = subprocess.run(
        [az_cmd, "bicep", "version"], capture_output=True, text=True, check=False,
        shell=(sys.platform == "win32"),
    )
    if proc.returncode != 0:
        raise SystemExit(
            "Azure CLI was found but the 'bicep' component isn't installed/working (`az bicep version` "
            f"failed):\n{proc.stderr or proc.stdout}\nRun 'az bicep install' (or 'az bicep upgrade') and "
            "retry."
        )


def _print_banner() -> None:
    """A short, friendly one-time header shown right before the first
    question, so the terminal reads like the start of a conversation rather
    than a raw stdin prompt with no context."""
    print("=" * 60)
    print("  Infra Composer Agent")
    print("  Describe what you want deployed -- I'll ask a few quick")
    print("  clarifying questions, then generate composed Bicep for it.")
    print("=" * 60)
    print()


def _print_essential_log(log: list[str]) -> None:
    """Prints only the log lines that matter for troubleshooting or final
    confirmation -- warnings/errors, and the main.bicep generation outcome.
    Routine bookkeeping (module counts, matched-resource detail, exclude/
    plan detail) is intentionally NOT re-printed here since it's already
    shown live during the interactive steps in interactive.py -- this avoids
    dumping the same information twice and keeps the console output focused
    on what actually needs attention."""
    keep_markers = ("WARNING", "Generated ", "validated successfully", "failed az bicep build", "skill version")
    for line in log:
        if any(line.startswith(m) or m in line for m in keep_markers):
            print(line)


def compose(prompt: str, source_root: Path, dest_root: Path,
            ai_foundry_endpoint: str | None = None, ai_foundry_model: str | None = None,
            ai_foundry_interpreter_agent_id: str | None = None,
            ai_foundry_author_agent_id: str | None = None,
            non_interactive: bool = False, readme_pattern: str = "ask",
            max_attempts: int | None = None) -> tuple[Path, list[str]]:
    """Runs the full pipeline. Returns (main_bicep_path, human_readable_log)."""
    log: list[str] = []
    if llm_composer.SKILL_VERSION:
        log.append(f"Using bicep-main-authoring skill version {llm_composer.SKILL_VERSION}")

    modules = build_index(source_root)
    log.append(f"Indexed {len(modules)} modules under {source_root}")

    endpoint = ai_foundry_endpoint or os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
    foundry_model = ai_foundry_model or os.environ.get("AI_FOUNDRY_MODEL_DEPLOYMENT")

    # Resource selection is now entirely conversational: the LLM reads the
    # real module catalog (never a predefined pattern catalog), asks
    # clarifying questions when it genuinely needs to, and proposes/revises
    # a plan with the user in the loop until it's confirmed. See
    # conversational_planner.py for the full loop and why there's no
    # deterministic pattern-matching/fuzzy-text-scoring here anymore.
    selected, requested_counts, existing_resource_notes, matched_pattern_id, plan_reasons = plan_resources_conversationally(
        prompt, modules, endpoint, foundry_model, non_interactive, log,
    )

    resolution = resolve(selected, modules)
    for key in resolution.modules:
        if key not in resolution.explicitly_requested:
            log.append(f"Auto-included dependency: {key}")
    for mod_key, pname in resolution.unresolved:
        log.append(f"WARNING: {mod_key} requires '{pname}' but no matching module/output was found; surfaced as a param")

    # Interactive unresolved-parameter resolution: ask whether to hardcode a
    # value for anything resolver.py couldn't wire up automatically, instead
    # of always silently surfacing it as a bare top-level parameter. These
    # user-supplied literals are threaded into the LLM's main.bicep authoring
    # prompt below (build_generation_prompt) so they still take effect even
    # though there is no deterministic template consuming them directly.
    param_defaults = interactive.resolve_unresolved_params(resolution, non_interactive, log)

    # Persist a human-reviewable build plan (PLAN.md) into the solution's own
    # output folder before main.bicep is authored -- see plan_doc.py for why
    # this mirrors microsoft/frontier-accelerator-factory's Planner Agent
    # writing solutions/<slug>/PLAN.md as a review boundary. Written into
    # dest_root (the staged output, same place main.bicep/README.md land) so
    # it travels with the generated solution rather than only existing in
    # this run's transient console/log output.
    dest_root.mkdir(parents=True, exist_ok=True)
    plan_path = plan_doc.write_plan_document(
        dest_root, prompt, matched_pattern_id, requested_counts, plan_reasons,
        resolution, param_defaults, existing_resource_notes,
    )
    log.append(f"Generated {plan_path}")

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
    effective_max_attempts = max_attempts if max_attempts is not None else llm_composer.DEFAULT_MAX_ATTEMPTS
    llm_code, gen_log, ok = generate_main_bicep_with_llm(
        prompt, resolution, requested_counts, dest_root, param_defaults, existing_resource_notes,
        ai_foundry_endpoint=endpoint, ai_foundry_model=foundry_model, ai_foundry_agent_id=author_agent_id,
        max_attempts=effective_max_attempts,
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
            max_attempts=effective_max_attempts,
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
    doc_paths = readme_gen.generate_docs(chosen_pattern, prompt, resolution, requested_counts, dest_root)
    for p in doc_paths:
        log.append(f"Generated {p}")

    return main_path, log


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].strip("-") or "infra"


def default_branch_name() -> str:
    """Simple, unique branch name -- deliberately NOT derived from the full
    --prompt text (that produced long, awkward names full of arbitrary
    prompt words). Uses a timestamp and a short random suffix so re-runs
    never collide."""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    short_id = uuid.uuid4().hex[:6]
    return f"infra/custom-{stamp}-{short_id}"



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
    parser.add_argument("--dest-name", default="infra-agents/bicep",
                         help="Folder (relative to the target repo root) to write the composition into. "
                              "Default 'infra-agents/bicep' keeps the generated main.bicep/modules/README.md "
                              "in their own bicep/ subfolder under infra-agents/, instead of the target repo "
                              "root. Pass '.' to write directly at the target repo root instead.")

    parser.add_argument("--ai-foundry-endpoint", default=None,
                         help="Azure AI Foundry project endpoint (required -- the agent always interprets "
                              "prompts and authors main.bicep via the Responses API, with no "
                              "deterministic fallback). Falls back to AI_FOUNDRY_PROJECT_ENDPOINT env var.")
    parser.add_argument("--ai-foundry-model", default=None,
                         help="Model deployment name (required -- sent on every Responses API call). "
                              "Falls back to AI_FOUNDRY_MODEL_DEPLOYMENT env var.")
    parser.add_argument("--ai-foundry-interpreter-agent-id", default=None,
                         help="Unused by the Responses API backend (accepted for backward compatibility "
                              "only). Falls back to AI_FOUNDRY_INTERPRETER_AGENT_ID env var.")
    parser.add_argument("--ai-foundry-author-agent-id", default=None,
                         help="Unused by the Responses API backend (accepted for backward compatibility "
                              "only). Falls back to AI_FOUNDRY_AUTHOR_AGENT_ID env var.")
    parser.add_argument("--validate", action="store_true", help="Run 'az bicep build' on the generated main.bicep.")
    parser.add_argument("--max-attempts", type=int, default=None,
                         help="Self-correction retry budget for main.bicep authoring/repair (both the "
                              "initial generation loop and the dedicated fixer pass). Defaults to "
                              "llm_composer.DEFAULT_MAX_ATTEMPTS (3, or INFRA_COMPOSER_MAX_ATTEMPTS env "
                              "var if set).")
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
    parser.add_argument("--no-git", action="store_true",
                         help="Skip cloning/branching/pushing entirely; just generate files locally under --dest-name.")
    parser.add_argument("--no-push", action="store_true",
                         help="Clone, branch, generate, and commit, but do not push to the remote.")
    parser.add_argument("--keep-clones", action="store_true",
                         help="Don't delete the temporary source/target clones after finishing (for inspection).")
    args = parser.parse_args()

    # Ask for the prompt FIRST, before any slow/blocking work (az CLI check,
    # network call to sync agent instructions to the Foundry portal) --
    # those can take several seconds and previously ran before the user ever
    # saw a question, making the CLI feel unresponsive/frozen on startup.
    # Asking immediately means the user is typing their answer while that
    # background validation happens, not staring at a blank terminal.
    if not args.prompt:
        if args.non_interactive:
            raise SystemExit("--prompt is required when --non-interactive is set (there is no one to ask).")
        _print_banner()
        prompt_text = input(
            "Describe the Azure infrastructure you'd like to deploy (e.g. \"a chat app with "
            "private networking and 2 storage accounts\"):\n> "
        ).strip()
        if not prompt_text:
            raise SystemExit("No description provided -- nothing to compose.")
        args.prompt = prompt_text
        print()  # breathing room before the setup/progress messages that follow

    # Fail fast on a missing/broken Azure CLI before any LLM calls are made
    # (every generation attempt is gated on `az bicep build`; discovering
    # this deep inside the retry loop would waste model calls on an
    # environment problem, not a prompt/model one).
    _check_az_bicep_available()

    ai_foundry_endpoint = args.ai_foundry_endpoint or os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
    if not ai_foundry_endpoint:
        raise SystemExit(
            "--ai-foundry-endpoint (or AI_FOUNDRY_PROJECT_ENDPOINT env var) is required: this agent always "
            "interprets prompts and authors main.bicep via Azure AI Foundry (Responses API) -- there "
            "is no deterministic/local fallback backend."
        )
    ai_foundry_model_for_sync = args.ai_foundry_model or os.environ.get("AI_FOUNDRY_MODEL_DEPLOYMENT")
    if not ai_foundry_model_for_sync:
        raise SystemExit(
            "--ai-foundry-model (or AI_FOUNDRY_MODEL_DEPLOYMENT env var) is required: the Responses API "
            "sends the model deployment name on every call (there's no pre-created agent with a model "
            "already baked in)."
        )

    # Best-effort: publish the agent DEFINITIONS (model + instructions) to the
    # AI Foundry portal's Agents tab for visibility, in sync with the local
    # source (conversational_planner.PLANNER_INSTRUCTIONS / llm_composer.SYSTEM_PROMPT).
    # This is purely for inspection -- the actual generation/interpretation calls
    # below go straight through the Responses API and never reference this
    # registration, so a sync failure (e.g. no Azure credentials / offline) is
    # non-fatal and only surfaced as a warning.
    try:
        import update_agent_instructions
        update_agent_instructions.sync_agent_instructions(ai_foundry_endpoint, ai_foundry_model_for_sync)
    except Exception as exc:
        print(f"WARNING: could not sync agent instructions, continuing without portal registration: {exc}\n")

    log: list[str] = []
    branch_name = args.branch_name or default_branch_name()
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
                                      max_attempts=args.max_attempts)
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

        # Run the whole interactive composition + main.bicep authoring
        # pipeline into a scratch staging directory FIRST, before touching
        # the target repo at all. compose() is the step most likely to be
        # aborted (declined confirmation, exhausted retry loop, main.bicep
        # authoring giving up after all repair attempts) -- cloning and
        # branching the target repo only after it succeeds means a failed
        # or abandoned run never leaves a stray clone/branch behind.
        staged_root = tmp_root / "staged"
        main_path, compose_log = compose(args.prompt, source_root, staged_root,
                                  ai_foundry_endpoint=args.ai_foundry_endpoint,
                                  ai_foundry_model=args.ai_foundry_model,
                                  ai_foundry_interpreter_agent_id=args.ai_foundry_interpreter_agent_id,
                                  ai_foundry_author_agent_id=args.ai_foundry_author_agent_id,
                                  non_interactive=args.non_interactive, readme_pattern=args.readme_pattern,
                                  max_attempts=args.max_attempts)
        log.extend(compose_log)
        _print_essential_log(log)

        if args.validate:
            ok, output = validate_with_az(main_path)
            print("VALIDATION:", "PASSED" if ok else "FAILED")
            if not ok:
                print(output)
                return 1

        target_repo_url = args.target_repo
        bot_name = bot_email = None
        if github_app_auth.is_configured():
            app_token = github_app_auth.get_installation_token()
            target_repo_url = github_app_auth.inject_token_into_url(args.target_repo, app_token)
            bot_name, bot_email = github_app_auth.get_app_bot_identity(token=app_token)

        print(f"Cloning target repo ({args.target_repo})...")
        git_ops.clone_repo(target_repo_url, target_clone_dir)

        print(f"Creating branch '{branch_name}'...")
        git_ops.create_branch_from_base(target_clone_dir, args.target_base, branch_name)

        # Copy the staged output into its real destination inside the target
        # clone. staged_root only ever contains files compose() itself wrote
        # (modules/, main.bicep, main.bicepparam, README.md, docs/), so a
        # wholesale copy-in is safe -- it never touches any other file
        # already in the target repo, even when --dest-name is "." (i.e.
        # dest_root == the repo root).
        dest_root = target_clone_dir if args.dest_name == "." else target_clone_dir / args.dest_name
        dest_root.mkdir(parents=True, exist_ok=True)
        for item in staged_root.iterdir():
            target_item = dest_root / item.name
            if item.is_dir():
                if target_item.exists():
                    shutil.rmtree(target_item)
                shutil.copytree(item, target_item)
            else:
                shutil.copy2(item, target_item)
        main_path = dest_root / main_path.relative_to(staged_root)

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
