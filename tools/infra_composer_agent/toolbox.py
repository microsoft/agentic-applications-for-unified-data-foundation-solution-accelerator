"""
Deterministic tool layer for the Planner Agent / Builder Agent
(.github/agents/planner-agent.agent.md, builder-agent.agent.md).

Those two are native GitHub Copilot custom agents: THEY do the reasoning
(matching a request to modules, deciding what's a Found vs. a Gap, authoring
main.bicep) using their own read/search/edit tools, instead of this project
calling out to a separate Azure AI Foundry Responses API model (that's what
agent.py/conversational_planner.py/llm_composer.py/foundry_client.py still do,
kept as the previous, independent CLI pipeline -- see README.md).

What the agents should NOT re-derive by hand, because it's already
deterministic, previously-tuned logic (fuzzy tag matching, CI-bootstrap
module exclusion, transitive local-module-ref copying, secret-usage
scanning, git plumbing) is exposed here as small, scriptable subcommands they
invoke via their `execute` tool. Every subcommand prints ONE JSON object to
stdout and exits non-zero on failure, so it's easy for an LLM agent to call
and parse.

Subcommands:
  catalog          -- scan a modules root, print the structural module index
  resolve          -- given selected module keys, print the full dependency
                       closure (including auto-included deps + unresolved params)
  compose          -- copy the resolved modules' .bicep files into a dest
                       project's modules/ folder, preserving relative layout
  validate         -- run `az bicep build` (+ this project's secret/lint gates)
                       against a main.bicep
  bicepparam       -- generate main.bicepparam from an authored main.bicep
  readme           -- generate README.md (+ optional DeploymentGuide.md)
  git-prepare      -- clone the target repo and create a new branch off its base
  git-commit-push  -- commit given paths in a repo clone and push the branch
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bicepparam_gen import generate_bicepparam
from composer import copy_modules
from module_index import ModuleInfo, build_index
from readme_gen import generate_docs
from resolver import ResolutionResult, resolve


def _module_to_dict(m: ModuleInfo) -> dict:
    return {
        "key": m.key,
        "flat_rel_path": str(m.flat_rel_path.as_posix()),
        "category": m.category,
        "name": m.name,
        "params": [
            {"name": p.name, "type": p.type, "required": p.required,
             "default": p.default, "description": p.description}
            for p in m.params
        ],
        "outputs": [
            {"name": o.name, "type": o.type, "description": o.description}
            for o in m.outputs
        ],
        "avm_refs": m.avm_refs,
        "tags": sorted(m.tags),
    }


def cmd_catalog(args: argparse.Namespace) -> dict:
    modules = build_index(Path(args.root))
    return {"root": args.root, "count": len(modules), "modules": [_module_to_dict(m) for m in modules]}


def _resolution_to_dict(resolution: ResolutionResult) -> dict:
    return {
        "modules": [_module_to_dict(m) for m in resolution.modules.values()],
        "order": list(resolution.modules.keys()),
        "explicitly_requested": sorted(resolution.explicitly_requested),
        "edges": {k: sorted(v) for k, v in resolution.edges.items()},
        "unresolved": [{"module": k, "param": p} for k, p in resolution.unresolved],
    }


def _select(all_modules: list[ModuleInfo], keys: list[str]) -> list[ModuleInfo]:
    by_key = {m.key: m for m in all_modules}
    missing = [k for k in keys if k not in by_key]
    if missing:
        raise SystemExit(f"Unknown module key(s), not found under --root: {missing}")
    return [by_key[k] for k in keys]


def cmd_resolve(args: argparse.Namespace) -> dict:
    all_modules = build_index(Path(args.root))
    selected = _select(all_modules, args.selected)
    resolution = resolve(selected, all_modules)
    return _resolution_to_dict(resolution)


def cmd_compose(args: argparse.Namespace) -> dict:
    root = Path(args.root)
    all_modules = build_index(root)
    selected = _select(all_modules, args.selected)
    resolution = resolve(selected, all_modules)
    dest_root = Path(args.dest)
    copied = copy_modules(resolution, root, dest_root)
    return {
        "dest": str(dest_root),
        "copied": {k: str(v) for k, v in copied.items()},
        "resolution": _resolution_to_dict(resolution),
    }


def cmd_validate(args: argparse.Namespace) -> dict:
    from bicep_validate import validate_with_az
    ok, output = validate_with_az(Path(args.file), strict=not args.no_strict)
    return {"file": args.file, "success": ok, "output": output}


def cmd_bicepparam(args: argparse.Namespace) -> dict:
    written = generate_bicepparam(Path(args.main), Path(args.dest), main_rel_path=args.main_rel_path)
    return {"written": str(written) if written else None}


def cmd_readme(args: argparse.Namespace) -> dict:
    root = Path(args.root)
    all_modules = build_index(root)
    counts: dict[str, int] = {}
    keys: list[str] = []
    for item in args.selected:
        key, _, count_str = item.partition(":")
        keys.append(key)
        counts[key] = int(count_str) if count_str else 1
    selected = _select(all_modules, keys)
    resolution = resolve(selected, all_modules)
    written = generate_docs(args.pattern, args.prompt, resolution, counts, Path(args.dest),
                             main_rel_path=args.main_rel_path)
    return {"written": [str(p) for p in written]}


def cmd_git_prepare(args: argparse.Namespace) -> dict:
    import git_ops
    workdir = Path(args.workdir)
    git_ops.clone_repo(args.target_repo, workdir)
    git_ops.create_branch_from_base(workdir, args.base_branch, args.new_branch)
    return {"repo_dir": str(workdir), "branch": args.new_branch}


def cmd_git_commit_push(args: argparse.Namespace) -> dict:
    import git_ops
    repo_dir = Path(args.repo_dir)
    result = git_ops.commit_paths(
        repo_dir, [Path(p) for p in args.paths], args.message,
        author_name=args.author_name, author_email=args.author_email,
    )
    push_result = None
    if not args.no_push:
        push_result = git_ops.push_branch(repo_dir, args.branch)
    return {"commit": result, "push": push_result}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic tool layer for the Planner/Builder Copilot agents.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_catalog = sub.add_parser("catalog", help="Scan a modules root and print the module index as JSON.")
    p_catalog.add_argument("--root", required=True, help="Path to the modules root (e.g. stable-cores/<project>/infra/bicep/modules).")
    p_catalog.set_defaults(func=cmd_catalog)

    p_resolve = sub.add_parser("resolve", help="Resolve the dependency closure for selected module keys.")
    p_resolve.add_argument("--root", required=True)
    p_resolve.add_argument("--selected", required=True, nargs="+", help="Module keys (from `catalog`'s 'key' field).")
    p_resolve.set_defaults(func=cmd_resolve)

    p_compose = sub.add_parser("compose", help="Copy selected + resolved modules into dest/modules/.")
    p_compose.add_argument("--root", required=True)
    p_compose.add_argument("--selected", required=True, nargs="+")
    p_compose.add_argument("--dest", required=True)
    p_compose.set_defaults(func=cmd_compose)

    p_validate = sub.add_parser("validate", help="Run `az bicep build` + secret/lint gates against a main.bicep.")
    p_validate.add_argument("--file", required=True)
    p_validate.add_argument("--no-strict", action="store_true", help="Allow linter warnings (still fails on hard errors and static-secret usage).")
    p_validate.set_defaults(func=cmd_validate)

    p_bicepparam = sub.add_parser("bicepparam", help="Generate main.bicepparam from an authored main.bicep.")
    p_bicepparam.add_argument("--main", required=True)
    p_bicepparam.add_argument("--dest", required=True)
    p_bicepparam.add_argument("--main-rel-path", default="main.bicep")
    p_bicepparam.set_defaults(func=cmd_bicepparam)

    p_readme = sub.add_parser("readme", help="Generate README.md (+ optional DeploymentGuide.md).")
    p_readme.add_argument("--pattern", required=True, choices=["solution-accelerator", "sample"])
    p_readme.add_argument("--root", required=True)
    p_readme.add_argument("--selected", required=True, nargs="+", help="Module keys, optionally 'key:count'.")
    p_readme.add_argument("--dest", required=True)
    p_readme.add_argument("--prompt", required=True)
    p_readme.add_argument("--main-rel-path", default="main.bicep")
    p_readme.set_defaults(func=cmd_readme)

    p_git_prepare = sub.add_parser("git-prepare", help="Clone the target repo and create a new branch off its base.")
    p_git_prepare.add_argument("--target-repo", required=True)
    p_git_prepare.add_argument("--base-branch", default="main")
    p_git_prepare.add_argument("--new-branch", required=True)
    p_git_prepare.add_argument("--workdir", required=True)
    p_git_prepare.set_defaults(func=cmd_git_prepare)

    p_git_push = sub.add_parser("git-commit-push", help="Commit given paths in a repo clone and push the branch.")
    p_git_push.add_argument("--repo-dir", required=True)
    p_git_push.add_argument("--paths", required=True, nargs="+")
    p_git_push.add_argument("--message", required=True)
    p_git_push.add_argument("--branch", required=True)
    p_git_push.add_argument("--author-name")
    p_git_push.add_argument("--author-email")
    p_git_push.add_argument("--no-push", action="store_true", help="Commit only, skip the push (e.g. for a dry run).")
    p_git_push.set_defaults(func=cmd_git_commit_push)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except Exception as exc:  # noqa: BLE001 -- surfaced to the calling agent as JSON, not a traceback
        print(json.dumps({"error": str(exc)}), file=sys.stdout)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
