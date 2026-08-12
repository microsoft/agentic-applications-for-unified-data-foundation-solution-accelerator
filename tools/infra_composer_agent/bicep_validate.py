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

`validate_with_az` also enforces this project's "always use managed identities/passwordless auth,
NEVER static credentials or secrets" rule (see skills/bicep-main-authoring.md and
skills/resource-planning.md) as a hard, programmatic gate -- not just documented guidance the LLM
might ignore. main.bicep is scanned for the ARM/Bicep functions and literal patterns that pull or
embed an access key/connection string (listKeys(), listConnectionStrings(), listSecrets(), or a
literal 'AccountKey='/'SharedAccessKey='/'DefaultEndpointsProtocol=' string). Any hit fails
validation exactly like a compile error, so the LLM's self-correction loop is forced to replace it
with a managed-identity/RBAC-based wiring instead (see resolver.py's role-assignment auto-inclusion).
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

# ARM/Bicep functions that retrieve a static access key or connection string
# from a resource -- the exact anti-pattern "always use managed identities,
# never static credentials/secrets" forbids. Matched as whole function calls
# so e.g. a module's own unrelated param named 'keyVaultName' never trips this.
_SECRET_FUNCTION_RE = re.compile(r"\blist(?:Keys|ConnectionStrings|Secrets|AccountSas|ServiceSas)\s*\(", re.IGNORECASE)

# Literal connection-string/SAS markers that indicate a hardcoded secret was
# embedded directly in the template rather than referenced via identity/RBAC.
_SECRET_LITERAL_RE = re.compile(
    r"(AccountKey=|SharedAccessKey=|DefaultEndpointsProtocol=|AccessKey=)", re.IGNORECASE
)


def _is_cli_noise(line: str) -> bool:
    return any(p.search(line) for p in _CLI_NOISE_PATTERNS)


def _check_no_secrets(main_bicep_text: str) -> list[str]:
    """Scans main.bicep's own source (never the vendored/copied modules
    under modules/, which this agent doesn't author) for access-key/
    connection-string patterns. Returns a list of human-readable violation
    messages (one per matched line), empty if none are found."""
    violations: list[str] = []
    for lineno, line in enumerate(main_bicep_text.splitlines(), start=1):
        if _SECRET_FUNCTION_RE.search(line):
            violations.append(
                f"line {lineno}: uses a key/connection-string-retrieving function ('{line.strip()}') -- "
                f"use a managed identity + RBAC role assignment instead, per the project's "
                f"no-static-credentials rule."
            )
        elif _SECRET_LITERAL_RE.search(line):
            violations.append(
                f"line {lineno}: appears to embed a literal connection string/access key "
                f"('{line.strip()}') -- use a managed identity + RBAC role assignment instead."
            )
    return violations


def _extract_lint_warnings(stderr: str, main_bicep: Path) -> list[str]:
    """Picks out only the lines that are genuine Bicep linter warnings ABOUT
    main.bicep ITSELF (the file the LLM actually authors and can fix),
    ignoring generic CLI nag lines AND warnings whose diagnostic path points
    at a different file -- almost always one of the vendored/copied module
    files under modules/, which the LLM never writes and has no way to
    change. Holding the LLM's retry loop to a bar that includes pre-existing
    warnings in someone else's module source is an impossible target (no
    amount of main.bicep rewriting can ever silence them), so those are
    intentionally excluded: only main.bicep's own diagnostics count toward
    "no issues at all"."""
    main_bicep_str = str(main_bicep)
    warnings = []
    for line in stderr.splitlines():
        if _is_cli_noise(line):
            continue
        if "Warning" not in line or ":" not in line:
            continue
        # Diagnostic lines are formatted as "<path>(<line>,<col>) : Warning ...".
        # Only keep the ones whose path matches main.bicep exactly.
        file_part = line.split("(", 1)[0].strip()
        if file_part == main_bicep_str:
            warnings.append(line.strip())
    return warnings


def validate_with_az(main_bicep: Path, strict: bool = True) -> tuple[bool, str]:
    """Runs 'az bicep build' against the given file. Returns (success, output).

    On a hard compile failure, output is the raw stderr (all diagnostics).
    On a clean compile, output is stdout (the compiled ARM JSON) UNLESS
    `strict` is True (the default) and the compile produced genuine Bicep
    linter warnings about main.bicep's OWN content -- in that case success
    is False and output lists those warnings, so the LLM retry loop treats
    "compiles but has linter warnings" the same as "fails to compile": this
    project's bar is a main.bicep with no issues at all, not merely one that
    technically compiles. Warnings whose diagnostic points at a DIFFERENT
    file (almost always a vendored/copied module under modules/, which the
    LLM never authors and cannot change) are never counted here -- see
    _extract_lint_warnings."""
    az_cmd = shutil.which("az") or shutil.which("az.cmd") or "az"
    proc = subprocess.run(
        [az_cmd, "bicep", "build", "--file", str(main_bicep), "--stdout"],
        capture_output=True, text=True, check=False, shell=(sys.platform == "win32"),
    )
    if proc.returncode != 0:
        return False, proc.stderr

    # Enforced regardless of `strict`: this is a hard security rule (no
    # static credentials/secrets), not a style preference that can be
    # relaxed like the lint-warning check below.
    secret_violations = _check_no_secrets(main_bicep.read_text(encoding="utf-8"))
    if secret_violations:
        violations_text = "\n".join(secret_violations)
        return False, (
            "main.bicep compiled successfully but violates the project's no-static-credentials rule "
            f"(always use managed identities/RBAC instead of access keys or connection strings):\n"
            f"{violations_text}"
        )

    if strict:
        lint_warnings = _extract_lint_warnings(proc.stderr, main_bicep)
        if lint_warnings:
            warnings_text = "\n".join(lint_warnings)
            return False, (
                "`az bicep build` compiled successfully but the Bicep linter reported the following "
                f"warning(s) in main.bicep itself, which must also be fixed:\n{warnings_text}"
            )

    return True, proc.stdout
