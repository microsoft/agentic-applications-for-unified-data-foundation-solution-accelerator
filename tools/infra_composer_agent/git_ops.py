"""
Git operations for the composer agent.

Creates an isolated branch based strictly on origin/<base_branch> (never
the currently checked-out branch), so the resulting branch contains only
the generated composition and none of the current working branch's
history or changes.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def run(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout.strip()


def create_isolated_branch(repo_root: Path, base_branch: str, new_branch: str) -> None:
    """Fetch base_branch and create/reset new_branch to point exactly at
    origin/<base_branch>, discarding any prior local history it may have had,
    so it never carries changes from the branch currently checked out."""
    run(["fetch", "origin", base_branch], repo_root)
    run(["checkout", "-B", new_branch, f"origin/{base_branch}"], repo_root)


def commit_paths(repo_root: Path, paths: list[Path], message: str) -> str:
    for p in paths:
        run(["add", "--", str(p)], repo_root)
    status = run(["status", "--porcelain"], repo_root)
    if not status:
        return "nothing to commit"
    return run(["commit", "-m", message], repo_root)
