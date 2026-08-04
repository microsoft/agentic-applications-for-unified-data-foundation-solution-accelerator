"""
CLI entry point for the infra composer agent.

Usage:
    python agent.py --prompt "2 storage accounts and 1 app service" \
        --source ../../infra_new/avm/modules --dest ../../generated-infra \
        [--validate] [--git-branch my-branch --git-base main]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from module_index import build_index, ModuleInfo
from request_parser import match_requests
from resolver import resolve
from composer import copy_modules, generate_main_bicep


def compose(prompt: str, source_root: Path, dest_root: Path) -> tuple[Path, list[str]]:
    """Runs the full pipeline. Returns (main_bicep_path, human_readable_log)."""
    log: list[str] = []

    modules = build_index(source_root)
    log.append(f"Indexed {len(modules)} modules under {source_root}")

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

    if dest_root.exists():
        shutil.rmtree(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)

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
    (dest_root / "README.md").write_text(readme, encoding="utf-8")

    return main_path, log


def validate_with_az(main_bicep: Path) -> tuple[bool, str]:
    az_cmd = shutil.which("az") or shutil.which("az.cmd") or "az"
    proc = subprocess.run(
        [az_cmd, "bicep", "build", "--file", str(main_bicep), "--stdout"],
        capture_output=True, text=True, check=False, shell=(sys.platform == "win32"),
    )
    return proc.returncode == 0, (proc.stdout if proc.returncode == 0 else proc.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compose deployable Bicep infra from existing modules based on a prompt.")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--dest", required=True, type=Path)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    main_path, log = compose(args.prompt, args.source.resolve(), args.dest.resolve())
    for line in log:
        print(line)

    if args.validate:
        ok, output = validate_with_az(main_path)
        print("VALIDATION:", "PASSED" if ok else "FAILED")
        if not ok:
            print(output)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
