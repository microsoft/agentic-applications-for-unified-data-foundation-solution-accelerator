"""
Git operations for the composer agent.

The agent always operates on two independently cloned repos in temp
directories, never on the working directory it happens to be invoked
from:
  - the SOURCE repo (fixed: the module library repo/branch), cloned
    read-only just to read modules from.
  - the TARGET repo (dynamic: whatever repo the caller names), cloned
    fresh each run, branched off its base branch, written into, committed,
    and pushed.

Cloning fresh copies -- rather than reusing/branching the directory the
agent's own source lives in -- means this is safe to run from inside the
very repository being modified, and safe to point at any target repo
without ever touching unrelated local branches or history.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def run(args: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout.strip()


def clone_repo(url: str, dest_dir: Path, branch: str | None = None) -> Path:
    """Clones `url` into dest_dir. If `branch` is given, clones that single
    branch's tip only (fast, read-only use -- e.g. the fixed source repo).
    If omitted, does a full clone of the default branch (needed for the
    target repo, where we still need `origin` configured to push a new
    branch afterward)."""
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    args = ["clone"]
    if branch:
        args += ["--branch", branch, "--single-branch", "--depth", "1"]
    args += [url, str(dest_dir)]
    run(args)
    return dest_dir


def create_branch_from_base(repo_dir: Path, base_branch: str, new_branch: str) -> None:
    """Fetches base_branch and creates new_branch pointing exactly at
    origin/<base_branch> -- never at whatever the clone's default checkout
    was -- so the new branch carries only history from the named base."""
    run(["fetch", "origin", base_branch], repo_dir)
    run(["checkout", "-B", new_branch, f"origin/{base_branch}"], repo_dir)


def commit_paths(repo_dir: Path, paths: list[Path], message: str,
                  author_name: str | None = None, author_email: str | None = None) -> str:
    """Commits `paths`. When `author_name`/`author_email` are given (e.g. a
    GitHub App's bot identity), sets them as this repo clone's local
    user.name/user.email first, so the commit is attributed to the app
    rather than whatever global git identity happens to be configured on
    the machine running the agent."""
    if author_name:
        run(["config", "user.name", author_name], repo_dir)
    if author_email:
        run(["config", "user.email", author_email], repo_dir)
    for p in paths:
        run(["add", "--", str(p)], repo_dir)
    status = run(["status", "--porcelain"], repo_dir)
    if not status:
        return "nothing to commit"
    return run(["commit", "-m", message], repo_dir)


def push_branch(repo_dir: Path, branch: str, remote: str = "origin") -> str:
    return run(["push", "-u", remote, branch], repo_dir)
