"""
Generates a `main.bicepparam` file for the composed project instead of a
`main.parameters.json` file, per the Bicep authoring guidance adopted into
skills/bicep-main-authoring.md (Section 13, itself following
https://github.com/microsoft/hve-core/blob/main/.github/instructions/coding-standards/bicep/bicep.instructions.md):
".bicepparam files support variables and expressions ... prefer them over
.json parameter files."

This module never asks the LLM to author the .bicepparam file itself -- it
deterministically parses the already-generated, already-validated
main.bicep (the same PARAM_RE used by module_index.py) to find every
top-level parameter that has no default value (i.e. must be supplied at
deploy time), and emits one `param <name> = <placeholder>` line per
parameter, each preceded by a `// <description>` comment pulled from the
param's own @description() decorator when present. This keeps the
generated .bicepparam always in sync with whatever the LLM actually wrote,
with no risk of hallucinating a parameter name that doesn't exist.
"""
from __future__ import annotations

import re
from pathlib import Path

from module_index import PARAM_RE, DESCRIPTION_RE


def _placeholder_for_type(type_str: str) -> str:
    t = type_str.strip().rstrip("?")
    if t == "string":
        return "'<REPLACE_ME>'"
    if t == "int":
        return "0"
    if t == "bool":
        return "false"
    if t == "array" or t.endswith("[]"):
        return "[]"
    if t == "object":
        return "{}"
    return "'<REPLACE_ME>'"


def required_top_level_params(main_bicep_text: str) -> list[tuple[str, str, str]]:
    """Returns (name, type, description) for every top-level `param` in
    main_bicep_text that has no default value assigned. Module-block
    `params: { ... }` entries are not matched by PARAM_RE (it only matches
    the `param <name> <type>` declaration syntax), so this only ever sees
    the orchestrator's own top-level parameters."""
    results = []
    for match in PARAM_RE.finditer(main_bicep_text):
        decorators, name, type_str, default = match.groups()
        if default is not None:
            continue
        desc_match = DESCRIPTION_RE.search(decorators or "")
        description = desc_match.group(1) if desc_match else ""
        results.append((name, type_str, description))
    return results


def generate_bicepparam(main_bicep_path: Path, dest_root: Path,
                         main_rel_path: str = "main.bicep") -> Path | None:
    """Writes main.bicepparam next to main.bicep with a `using` statement and
    one placeholder `param` assignment per required top-level parameter.
    Returns the written path, or None if there are no required parameters
    to scaffold (nothing useful to generate)."""
    text = main_bicep_path.read_text(encoding="utf-8")
    required = required_top_level_params(text)
    if not required:
        return None

    lines = [f"using '{main_rel_path}'", ""]
    for name, type_str, description in required:
        if description:
            lines.append(f"// {description}")
        lines.append(f"param {name} = {_placeholder_for_type(type_str)}")
        lines.append("")

    bicepparam_path = dest_root / "main.bicepparam"
    bicepparam_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return bicepparam_path
