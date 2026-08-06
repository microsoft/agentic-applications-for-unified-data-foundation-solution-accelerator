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
from pathlib import Path

import git_ops
from module_index import build_index, ModuleInfo
from request_parser import match_requests
from resolver import resolve
from composer import copy_modules, generate_main_bicep
from llm_interpreter import interpret_with_llm, DEFAULT_OLLAMA_HOST, DEFAULT_OLLAMA_MODEL
from llm_composer import generate_main_bicep_with_llm, fix_bicep_with_llm
from bicep_validate import validate_with_az
import interactive
import readme_gen
import tech_patterns

# Fixed source: the module library this agent always composes from.
DEFAULT_SOURCE_REPO = "https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator.git"
DEFAULT_SOURCE_BRANCH = "infra-core-modules-copy"
DEFAULT_SOURCE_PATH = "infra_new/avm/modules"


def _interpret_requests(text: str, modules: list[ModuleInfo], use_llm: bool, llm_backend: str,
                         ollama_host: str | None, ollama_model: str | None,
                         ai_foundry_endpoint: str | None, ai_foundry_model: str | None,
                         ai_foundry_interpreter_agent_id: str | None, log: list[str]):
    """Runs the same prompt -> ResourceRequest interpretation (LLM or
    deterministic matcher) used for the initial prompt, factored out so the
    interactive 'add more resources' loop in compose() can reuse it verbatim
    on whatever free text the user adds afterwards."""
    if use_llm:
        host = ollama_host or os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
        model = ollama_model or os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        endpoint = ai_foundry_endpoint or os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
        foundry_model = ai_foundry_model or os.environ.get("AI_FOUNDRY_MODEL_DEPLOYMENT")
        interpreter_agent_id = ai_foundry_interpreter_agent_id or os.environ.get("AI_FOUNDRY_INTERPRETER_AGENT_ID")
        return interpret_with_llm(
            text, modules, backend=llm_backend,
            ollama_host=host, ollama_model=model,
            project_endpoint=endpoint, model_deployment=foundry_model, agent_id=interpreter_agent_id,
        )
    return match_requests(text, modules)


def compose(prompt: str, source_root: Path, dest_root: Path,
            use_llm: bool = False, llm_backend: str = "ollama",
            ollama_host: str | None = None, ollama_model: str | None = None,
            ai_foundry_endpoint: str | None = None, ai_foundry_model: str | None = None,
            ai_foundry_interpreter_agent_id: str | None = None,
            ai_foundry_author_agent_id: str | None = None,
            non_interactive: bool = False, readme_pattern: str = "ask",
            tech_pattern: str | None = None) -> tuple[Path, list[str]]:
    """Runs the full pipeline. Returns (main_bicep_path, human_readable_log)."""
    log: list[str] = []

    modules = build_index(source_root)
    log.append(f"Indexed {len(modules)} modules under {source_root}")

    # Technical-pattern seeding: if a predefined pattern (chat-with-data,
    # document-processing, call-center, realtime-alerts -- see
    # tech_patterns.py) applies, prepend its baseline resource_prompt to the
    # user's free-text prompt *before* interpretation, so the pattern's
    # resources are always included alongside anything the user described
    # themselves. The user still sees and can add to/trim the resolved list
    # via the existing confirm_resources() interactive loop below.
    chosen_tech_pattern = interactive.choose_tech_pattern(prompt, tech_pattern, non_interactive, log)
    effective_prompt = prompt
    if chosen_tech_pattern:
        pattern = tech_patterns.PATTERNS[chosen_tech_pattern]
        log.append(
            f"Seeding composition from the '{chosen_tech_pattern}' technical pattern "
            f"({pattern.display_name}): {', '.join(pattern.key_resources)}."
        )
        effective_prompt = f"{pattern.resource_prompt}\n\n{prompt.strip()}".strip()

    if use_llm:
        backend_desc = ("local Ollama model" if llm_backend == "ollama"
                         else "the persistent AI Foundry agent 'infra-composer-prompt-interpreter'")
        log.append(f"Interpreting prompt via {backend_desc}...")
    requests = _interpret_requests(
        effective_prompt, modules, use_llm, llm_backend, ollama_host, ollama_model,
        ai_foundry_endpoint, ai_foundry_model, ai_foundry_interpreter_agent_id, log,
    )
    if use_llm:
        log.append(f"LLM identified {len(requests)} resource concept(s) from the prompt.")

    selected: list[ModuleInfo] = []
    requested_counts: dict[str, int] = {}
    for req in requests:
        if req.matched_module is None:
            log.append(f"WARNING: could not match request '{req.text.strip()}' to any module (skipped)")
            continue
        log.append(
            f"Matched '{req.text.strip()}' -> {req.matched_module.key} "
            f"(score={req.score:.2f}, count={req.count})"
        )
        selected.append(req.matched_module)
        requested_counts[req.matched_module.key] = req.count

    if not selected:
        raise SystemExit("No resources could be matched from the prompt. Aborting.")

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
        extra_requests = _interpret_requests(
            addition_text, modules, use_llm, llm_backend, ollama_host, ollama_model,
            ai_foundry_endpoint, ai_foundry_model, ai_foundry_interpreter_agent_id, log,
        )
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
    # of always silently surfacing it as a bare top-level parameter.
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
    if use_llm:
        log.append("Generating main.bicep with the LLM (architect-style: feature flags, conditionals, "
                    "wired outputs) instead of the flat deterministic template...")
        host = ollama_host or os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
        model = ollama_model or os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        endpoint = ai_foundry_endpoint or os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
        foundry_model = ai_foundry_model or os.environ.get("AI_FOUNDRY_MODEL_DEPLOYMENT")
        author_agent_id = ai_foundry_author_agent_id or os.environ.get("AI_FOUNDRY_AUTHOR_AGENT_ID")
        llm_code, gen_log, ok = generate_main_bicep_with_llm(
            effective_prompt, resolution, requested_counts, dest_root, backend=llm_backend,
            ollama_host=host, ollama_model=model,
            ai_foundry_endpoint=endpoint, ai_foundry_model=foundry_model, ai_foundry_agent_id=author_agent_id,
        )
        log.extend(gen_log)
        if not ok:
            log.append("LLM-authored main.bicep did not pass validation after all retries; falling back "
                        "to the deterministic template generator so the output remains guaranteed-deployable.")
            main_bicep = generate_main_bicep(resolution, requested_counts, param_defaults)
            main_path.write_text(main_bicep, encoding="utf-8")

            fallback_ok, fallback_errors = validate_with_az(main_path)
            if not fallback_ok:
                log.append("WARNING: the deterministic fallback template also failed az bicep build "
                            "validation -- invoking the persistent author agent as a dedicated fixer to "
                            "patch the real errors instead of shipping an unvalidated file.")
                _, fix_log, fixed = fix_bicep_with_llm(
                    main_path, fallback_errors, backend=llm_backend,
                    ollama_host=host, ollama_model=model,
                    ai_foundry_endpoint=endpoint, ai_foundry_model=foundry_model,
                    ai_foundry_agent_id=author_agent_id, source_label="deterministic fallback main.bicep",
                )
                log.extend(fix_log)
                if not fixed:
                    log.append("WARNING: the fixer agent could not repair main.bicep either -- the file at "
                                f"{main_path} still fails validation and must be fixed by hand before deploying.")
    else:
        main_bicep = generate_main_bicep(resolution, requested_counts, param_defaults)
        main_path.write_text(main_bicep, encoding="utf-8")
    log.append(f"Generated {main_path}")

    chosen_pattern = interactive.choose_readme_pattern(effective_prompt, readme_pattern, non_interactive, log)
    doc_paths = readme_gen.generate_docs(chosen_pattern, prompt, resolution, requested_counts, dest_root,
                                          tech_pattern=chosen_tech_pattern)
    for p in doc_paths:
        log.append(f"Generated {p}")

    return main_path, log


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].strip("-") or "infra"


def default_branch_name(prompt: str) -> str:
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"infra/{slugify(prompt)}-{stamp}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compose deployable Bicep infra from the fixed module library, "
                    "then branch/commit/push it into the ROOT of any target repo."
    )
    parser.add_argument("--prompt", required=True, help="Natural-language infra request, e.g. '2 storage accounts and 1 app service'.")

    parser.add_argument("--source-repo", default=DEFAULT_SOURCE_REPO,
                         help=f"Module library repo (fixed by default: {DEFAULT_SOURCE_REPO}).")
    parser.add_argument("--source-branch", default=DEFAULT_SOURCE_BRANCH,
                         help=f"Branch of the module library repo (default: {DEFAULT_SOURCE_BRANCH}).")
    parser.add_argument("--source-path", default=DEFAULT_SOURCE_PATH,
                         help=f"Path within the source repo to the modules root (default: {DEFAULT_SOURCE_PATH}).")

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

    parser.add_argument("--use-llm", action="store_true",
                         help="Interpret --prompt with an LLM first (handles messier, intent-driven prompts "
                              "involving RBAC/role assignments/connections instead of plain resource counts). "
                              "No fallback: if the chosen backend fails, the run stops with an error.")
    parser.add_argument("--llm-backend", default="ollama", choices=["ollama", "ai-foundry"],
                         help="Which LLM backend to use with --use-llm (default: ollama -- local, free, offline).")
    parser.add_argument("--ollama-host", default=None,
                         help=f"Local Ollama server URL (default: {DEFAULT_OLLAMA_HOST}). Falls back to OLLAMA_HOST env var.")
    parser.add_argument("--ollama-model", default=None,
                         help=f"Ollama model to use (default: {DEFAULT_OLLAMA_MODEL}). Falls back to OLLAMA_MODEL env var. "
                              "Must already be pulled locally (`ollama pull <model>`).")
    parser.add_argument("--ai-foundry-endpoint", default=None,
                         help="Azure AI Foundry project endpoint (only used with --llm-backend ai-foundry). "
                              "Falls back to AI_FOUNDRY_PROJECT_ENDPOINT env var.")
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

    branch_name = args.branch_name or default_branch_name(args.prompt)
    tmp_root = Path(tempfile.mkdtemp(prefix="infra-composer-"))
    source_clone_dir = tmp_root / "source"
    target_clone_dir = tmp_root / "target"

    try:
        print(f"Cloning source module library ({args.source_repo} @ {args.source_branch})...")
        git_ops.clone_repo(args.source_repo, source_clone_dir, branch=args.source_branch)
        source_root = source_clone_dir / args.source_path

        if args.no_git:
            dest_root = tmp_root / "generated-infra" if args.dest_name == "." else Path(args.dest_name).resolve()
            main_path, log = compose(args.prompt, source_root, dest_root,
                                      use_llm=args.use_llm, llm_backend=args.llm_backend,
                                      ollama_host=args.ollama_host, ollama_model=args.ollama_model,
                                      ai_foundry_endpoint=args.ai_foundry_endpoint,
                                      ai_foundry_model=args.ai_foundry_model,
                                      ai_foundry_interpreter_agent_id=args.ai_foundry_interpreter_agent_id,
                                      ai_foundry_author_agent_id=args.ai_foundry_author_agent_id,
                                      non_interactive=args.non_interactive, readme_pattern=args.readme_pattern,
                                      tech_pattern=args.tech_pattern)
            for line in log:
                print(line)
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

        print(f"Cloning target repo ({args.target_repo})...")
        git_ops.clone_repo(args.target_repo, target_clone_dir)

        print(f"Creating branch '{branch_name}' in the target repo, based strictly on origin/{args.target_base} "
              f"(no other branch's history included)...")
        git_ops.create_branch_from_base(target_clone_dir, args.target_base, branch_name)

        dest_root = target_clone_dir if args.dest_name == "." else target_clone_dir / args.dest_name
        main_path, log = compose(args.prompt, source_root, dest_root,
                                  use_llm=args.use_llm, llm_backend=args.llm_backend,
                                  ollama_host=args.ollama_host, ollama_model=args.ollama_model,
                                  ai_foundry_endpoint=args.ai_foundry_endpoint,
                                  ai_foundry_model=args.ai_foundry_model,
                                  ai_foundry_interpreter_agent_id=args.ai_foundry_interpreter_agent_id,
                                  ai_foundry_author_agent_id=args.ai_foundry_author_agent_id,
                                  non_interactive=args.non_interactive, readme_pattern=args.readme_pattern,
                                  tech_pattern=args.tech_pattern)
        for line in log:
            print(line)

        if args.validate:
            ok, output = validate_with_az(main_path)
            print("VALIDATION:", "PASSED" if ok else "FAILED")
            if not ok:
                print(output)
                return 1

        message = (
            f"Add generated infra composition: {args.prompt}\n\n"
            f"Auto-generated by infra_composer_agent from the above natural-language request, "
            f"composed from {args.source_repo}@{args.source_branch}:{args.source_path}.\n\n"
            f"Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
        )
        result = git_ops.commit_paths(target_clone_dir, [dest_root], message)
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
