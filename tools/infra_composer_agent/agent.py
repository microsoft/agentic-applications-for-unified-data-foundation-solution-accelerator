"""
CLI entry point for the infra composer agent.

The module SOURCE is fixed by default: the AVM Bicep module library that
lives in this repo on the `infra-core-modules-copy` branch, under
`infra_new/avm/modules`. It is cloned fresh (read-only, shallow) every run
so the agent always works from a clean, known copy regardless of where it
is invoked from.

The TARGET is dynamic: pass any repository URL via --target-repo. Each run
clones that repo fresh, creates a brand-new branch off its base branch
(default `main`), generates the composed Bicep project at the ROOT of that
checkout, commits, and pushes -- so the same command can be pointed at a
different repo (or the same repo again) every time with different results,
driven entirely by --prompt and --target-repo.

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
from llm_interpreter import interpret_with_llm

# Fixed source: the module library this agent always composes from.
DEFAULT_SOURCE_REPO = "https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator.git"
DEFAULT_SOURCE_BRANCH = "infra-core-modules-copy"
DEFAULT_SOURCE_PATH = "infra_new/avm/modules"


def compose(prompt: str, source_root: Path, dest_root: Path,
            use_llm: bool = False, ai_foundry_endpoint: str | None = None,
            ai_foundry_model: str | None = None, ai_foundry_agent_id: str | None = None
            ) -> tuple[Path, list[str]]:
    """Runs the full pipeline. Returns (main_bicep_path, human_readable_log)."""
    log: list[str] = []

    modules = build_index(source_root)
    log.append(f"Indexed {len(modules)} modules under {source_root}")

    requests = None
    if use_llm:
        endpoint = ai_foundry_endpoint or os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
        model = ai_foundry_model or os.environ.get("AI_FOUNDRY_MODEL_DEPLOYMENT")
        agent_id = ai_foundry_agent_id or os.environ.get("AI_FOUNDRY_AGENT_ID")
        if not endpoint or not model:
            log.append("LLM interpretation requested but AI_FOUNDRY_PROJECT_ENDPOINT/"
                        "AI_FOUNDRY_MODEL_DEPLOYMENT are not set; falling back to deterministic matching.")
        else:
            log.append(f"Interpreting prompt via Azure AI Foundry agent at {endpoint} (model={model})...")
            requests = interpret_with_llm(prompt, modules, endpoint, model, agent_id)
            if requests is not None:
                log.append(f"LLM identified {len(requests)} resource concept(s) from the prompt.")

    if requests is None:
        requests = match_requests(prompt, modules)
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

    main_bicep = generate_main_bicep(resolution, requested_counts)
    main_path = dest_root / "main.bicep"
    main_path.write_text(main_bicep, encoding="utf-8")
    log.append(f"Generated {main_path}")

    readme = (
        f"# Generated infrastructure composition\n\n"
        f"Composed automatically by `infra_composer_agent` from the request:\n\n"
        f"> {prompt}\n\n"
        f"## Modules included\n\n"
        + "\n".join(f"- `{k}`" + ("" if k in resolution.explicitly_requested else "  _(auto-included dependency)_")
                     for k in resolution.modules)
        + "\n\nDeploy with:\n\n```\naz deployment group create --resource-group <rg> --template-file main.bicep\n```\n"
    )
    # Use a distinct filename (never "README.md") so this never collides with
    # -- and never overwrites -- a pre-existing README at the destination,
    # which matters most when dest_root is the target repo's own root.
    readme_path = dest_root / "INFRA_COMPOSITION.md"
    readme_path.write_text(readme, encoding="utf-8")
    log.append(f"Generated {readme_path}")

    return main_path, log


def validate_with_az(main_bicep: Path) -> tuple[bool, str]:
    az_cmd = shutil.which("az") or shutil.which("az.cmd") or "az"
    proc = subprocess.run(
        [az_cmd, "bicep", "build", "--file", str(main_bicep), "--stdout"],
        capture_output=True, text=True, check=False, shell=(sys.platform == "win32"),
    )
    return proc.returncode == 0, (proc.stdout if proc.returncode == 0 else proc.stderr)


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
    parser.add_argument("--dest-name", default=".",
                         help="Folder (relative to the target repo root) to write the composition into. "
                              "Default '.' places main.bicep/modules/README.md directly at the target repo root.")

    parser.add_argument("--use-llm", action="store_true",
                         help="Interpret --prompt with an Azure AI Foundry agent first (handles messier, "
                              "intent-driven prompts involving RBAC/role assignments/connections), falling "
                              "back to the deterministic matcher if AI Foundry isn't configured or fails.")
    parser.add_argument("--ai-foundry-endpoint", default=None,
                         help="Azure AI Foundry project endpoint. Falls back to AI_FOUNDRY_PROJECT_ENDPOINT env var.")
    parser.add_argument("--ai-foundry-model", default=None,
                         help="Model deployment name in the AI Foundry project (e.g. gpt-4o). "
                              "Falls back to AI_FOUNDRY_MODEL_DEPLOYMENT env var.")
    parser.add_argument("--ai-foundry-agent-id", default=None,
                         help="Reuse an existing AI Foundry agent instead of creating/deleting a temporary one. "
                              "Falls back to AI_FOUNDRY_AGENT_ID env var.")
    parser.add_argument("--validate", action="store_true", help="Run 'az bicep build' on the generated main.bicep.")
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
                                      use_llm=args.use_llm, ai_foundry_endpoint=args.ai_foundry_endpoint,
                                      ai_foundry_model=args.ai_foundry_model, ai_foundry_agent_id=args.ai_foundry_agent_id)
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
                                  use_llm=args.use_llm, ai_foundry_endpoint=args.ai_foundry_endpoint,
                                  ai_foundry_model=args.ai_foundry_model, ai_foundry_agent_id=args.ai_foundry_agent_id)
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
