"""
Shared Bicep validation helper (used by both the deterministic pipeline and
the LLM-based main.bicep generator, kept in one place to avoid duplication
and circular imports).

IMPORTANT: `az bicep build` exits 0 (success) even when the Bicep linter
reports warnings (e.g. no-unused-params, no-hardcoded-env-urls, prefer-unquoted-property-names) --
it only fails the process on hard compile errors. Since this project's goal is a main.bicep with
NO issues at all (not just "compiles"), `validate_with_az` treats any linter warning that is
actually about the Bicep file's own content as a failure too, so it gets fed back into the LLM's
self-correction retry loop exactly like a hard error. CLI "nag" warnings that have nothing to do
with the file's content (new-version-available nudges, subscription/telemetry notices) are
filtered out so they never cause a spurious retry loop.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

# Lines the Azure CLI prints on stderr that are pure CLI/environment noise,
# never an actual problem with the Bicep file's own content -- must never
# trigger a retry.
_CLI_NOISE_PATTERNS = [
    re.compile(r"A new Bicep release is available", re.IGNORECASE),
    re.compile(r"upgrade.*bicep upgrade", re.IGNORECASE),
    re.compile(r"You have \d+ update\(s\) available", re.IGNORECASE),
    re.compile(r"^\s*$"),
]


def _is_cli_noise(line: str) -> bool:
    return any(p.search(line) for p in _CLI_NOISE_PATTERNS)


def _extract_lint_warnings(stderr: str) -> list[str]:
    """Picks out only the lines that are genuine Bicep linter warnings about
    the file itself (contain a 'Warning <rule-name>:' diagnostic), ignoring
    generic CLI nag lines."""
    warnings = []
    for line in stderr.splitlines():
        if _is_cli_noise(line):
            continue
        if "Warning" in line and ":" in line:
            warnings.append(line.strip())
    return warnings


def validate_with_az(main_bicep: Path, strict: bool = True) -> tuple[bool, str]:
    """Runs 'az bicep build' against the given file. Returns (success, output).

    On a hard compile failure, output is the raw stderr (all diagnostics).
    On a clean compile, output is stdout (the compiled ARM JSON) UNLESS
    `strict` is True (the default) and the compile produced genuine Bicep
    linter warnings about the file's own content -- in that case success is
    False and output lists those warnings, so the LLM retry loop treats
    "compiles but has linter warnings" the same as "fails to compile": this
    project's bar is a main.bicep with no issues at all, not merely one that
    technically compiles."""
    az_cmd = shutil.which("az") or shutil.which("az.cmd") or "az"
    proc = subprocess.run(
        [az_cmd, "bicep", "build", "--file", str(main_bicep), "--stdout"],
        capture_output=True, text=True, check=False, shell=(sys.platform == "win32"),
    )
    if proc.returncode != 0:
        return False, proc.stderr

    if strict:
        lint_warnings = _extract_lint_warnings(proc.stderr)
        if lint_warnings:
            warnings_text = "\n".join(lint_warnings)
            return False, (
                "`az bicep build` compiled successfully but the Bicep linter reported the following "
                f"warning(s), which must also be fixed:\n{warnings_text}"
            )

    return True, proc.stdout
