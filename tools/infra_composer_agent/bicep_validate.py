"""
Shared Bicep validation helper (used by both the deterministic pipeline and
the LLM-based main.bicep generator, kept in one place to avoid duplication
and circular imports).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def validate_with_az(main_bicep: Path) -> tuple[bool, str]:
    """Runs 'az bicep build' against the given file. Returns (success, output)
    where output is stdout on success or stderr on failure."""
    az_cmd = shutil.which("az") or shutil.which("az.cmd") or "az"
    proc = subprocess.run(
        [az_cmd, "bicep", "build", "--file", str(main_bicep), "--stdout"],
        capture_output=True, text=True, check=False, shell=(sys.platform == "win32"),
    )
    return proc.returncode == 0, (proc.stdout if proc.returncode == 0 else proc.stderr)
