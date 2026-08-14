"""
Persisted build-plan document.

Writes a human-reviewable PLAN.md into the generated solution's own output
folder, alongside main.bicep -- a persisted record of what was planned and
why, instead of that information only ever existing transiently in the
console/log during the interactive session.

This is modeled on microsoft/frontier-accelerator-factory's Planner Agent,
which writes solutions/<slug>/PLAN.md as an explicit review boundary before
its separate Builder Agent executes it. That repo's plan can have genuine
"Gap" entries needing net-new code, because it composes from three source
layers (stable core + technical pattern + industry scenario) that don't
always fully cover a request. This project only ever composes from ONE flat
module catalog and always reuses real modules verbatim -- it never invents
a module -- so there's no equivalent of "Gap = net-new code" here. The one
place a request's needs sometimes can't be satisfied by an existing
module/output wiring is a required parameter with no matching module or
output (see resolver.py's `unresolved` list); that's the meaningful
Found/Gap-style distinction for this project, and PLAN.md's capability
table surfaces it explicitly so it's reviewable after the run, not just a
one-off console prompt with no persisted record.
"""
from __future__ import annotations

from pathlib import Path

from resolver import ResolutionResult


def write_plan_document(
    dest_root: Path,
    prompt: str,
    matched_pattern_id: str | None,
    requested_counts: dict[str, int],
    plan_reasons: dict[str, str],
    resolution: ResolutionResult,
    param_defaults: dict[str, str],
    existing_resource_notes: list[str],
) -> Path:
    """Writes dest_root/PLAN.md and returns the path written."""
    lines: list[str] = []
    lines.append("# Infrastructure build plan")
    lines.append("")
    lines.append(f"**Request:** {prompt}")
    lines.append("")
    lines.append(
        f"**Matched technical pattern:** "
        f"{matched_pattern_id or '_none -- planned from the free-text request alone_'}"
    )
    lines.append("")

    if existing_resource_notes:
        lines.append("## Existing resources to reuse")
        lines.append("")
        for note in existing_resource_notes:
            lines.append(f"- {note}")
        lines.append("")

    lines.append("## Capability inventory")
    lines.append("")
    lines.append("| Module / parameter | Status | Count | Detail |")
    lines.append("|---|---|---|---|")
    for key, module in resolution.modules.items():
        count = requested_counts.get(key, 1)
        reason = plan_reasons.get(key, "")
        status = "Found (requested)" if key in resolution.explicitly_requested else "Found (auto-included dependency)"
        lines.append(f"| `{key}` | {status} | {count} | {reason} |")
    for mod_key, pname in resolution.unresolved:
        override = param_defaults.get(f"{mod_key}::{pname}")
        detail = f"hardcoded to `{override}`" if override else "left as a required top-level parameter"
        lines.append(f"| `{mod_key}` (param `{pname}`) | Gap -- no module/output satisfies this | -- | {detail} |")
    lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append(
        "This plan was produced by the Infra Composer Agent's conversational planner before "
        "main.bicep was authored. Every \"Found\" module key is copied verbatim from the real "
        "module catalog on disk -- nothing here is invented. Review this file before deploying; "
        "if changes are needed, edit modules/, main.bicep, or main.bicepparam directly and re-run "
        "if you want the plan regenerated."
    )
    lines.append("")

    text = "\n".join(lines)
    plan_path = dest_root / "PLAN.md"
    plan_path.write_text(text, encoding="utf-8")
    return plan_path
