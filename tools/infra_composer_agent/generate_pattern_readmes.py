"""
One-off/repeatable script that (re)populates the placeholder README.md files
under 001-wip-repo-structure/technical-patterns/<id>/README.md from the
tech_patterns.py catalog, which is the single source of truth for pattern
content.

Usage (from repo root or anywhere -- paths are resolved relative to this
file's location):
    python tools/infra_composer_agent/generate_pattern_readmes.py
"""
from __future__ import annotations

from pathlib import Path

from tech_patterns import PATTERNS, render_readme

REPO_ROOT = Path(__file__).resolve().parents[2]
PATTERNS_ROOT = REPO_ROOT / "001-wip-repo-structure" / "technical-patterns"


def main() -> int:
    if not PATTERNS_ROOT.exists():
        print(f"Technical-patterns folder not found at {PATTERNS_ROOT}; nothing to do.")
        return 1

    for pattern_id, pattern in PATTERNS.items():
        pattern_dir = PATTERNS_ROOT / pattern_id
        if not pattern_dir.exists():
            print(f"Skipping '{pattern_id}': no folder at {pattern_dir}")
            continue
        readme_path = pattern_dir / "README.md"
        readme_path.write_text(render_readme(pattern), encoding="utf-8")
        print(f"Wrote {readme_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
