"""
Interactive CLI prompts for the infra composer agent.

Keeps the agent conversational at well-defined decision points instead of
silently guessing:
  1. Which README / deployment-doc pattern to generate (see readme_gen.py).
  2. What to do about any required module parameter that has no matching
     local module/output (surfaced by resolver.py as `unresolved`) --
     hardcode a value now, or leave it as a top-level parameter.

Resource selection itself (which modules to use, how many, and any
clarifying questions about the request) is handled entirely by
conversational_planner.py -- there is no predefined pattern catalog here
anymore (see conversational_planner.py's module docstring for why).

Every prompt has a safe, documented default and is skipped entirely when
non_interactive=True (the --non-interactive CLI flag), so the exact same
pipeline still runs unattended in scripts/CI.
"""
from __future__ import annotations

from resolver import ResolutionResult

README_PATTERNS = {
    "solution-accelerator": (
        "Solution-accelerator style: README.md + docs/DeploymentGuide.md, modeled on "
        "microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator (richer, "
        "step-by-step deployment doc)."
    ),
    "sample": (
        "Sample style: a single README.md with a Mermaid architecture diagram, modeled on "
        "Azure-Samples/chat-with-your-data-solution-accelerator (simpler, no separate guide)."
    ),
}

_SOLUTION_ACCELERATOR_HINTS = (
    "azd", "solution accelerator", "deployment guide", "codespaces", "dev container", "quick deploy",
)
_SAMPLE_HINTS = ("mermaid", "simple sample", "single readme", "lightweight", "minimal readme")


def _infer_pattern(prompt: str) -> str | None:
    lower = prompt.lower()
    if any(h in lower for h in _SOLUTION_ACCELERATOR_HINTS):
        return "solution-accelerator"
    if any(h in lower for h in _SAMPLE_HINTS):
        return "sample"
    return None


def choose_readme_pattern(prompt: str, requested_pattern: str, non_interactive: bool, log: list[str]) -> str:
    """Resolves which README pattern to generate. `requested_pattern` is the
    --readme-pattern CLI value: an explicit 'solution-accelerator'/'sample'
    always wins outright. Otherwise this is auto-decided (inferred from the
    prompt, falling back to 'solution-accelerator') WITHOUT asking -- this is
    a low-stakes, easy-to-change-later choice, so it doesn't warrant its own
    interactive round-trip on every run. The choice is still announced so
    it's never silent/invisible."""
    if requested_pattern in README_PATTERNS:
        log.append(f"Using README pattern '{requested_pattern}' (from --readme-pattern).")
        return requested_pattern

    inferred = _infer_pattern(prompt)
    chosen = inferred or "solution-accelerator"
    log.append(
        f"Using README pattern '{chosen}'"
        + (" (inferred from prompt)" if inferred else " (default)")
        + f" -- {README_PATTERNS[chosen]}"
    )
    return chosen


def resolve_unresolved_params(resolution: ResolutionResult, non_interactive: bool,
                               log: list[str]) -> dict[str, str]:
    """For each (module_key, param_name) resolver.py couldn't auto-wire to any
    local module/output, optionally ask the user for a literal value to bake
    in directly instead of always surfacing it as a bare top-level parameter.
    Returns {"<module_key>::<param_name>": "<raw literal>"} for whatever the
    user actually supplied (never all of them -- entries left blank fall
    through to composer.py's existing top-level-parameter fallback)."""
    overrides: dict[str, str] = {}
    if not resolution.unresolved:
        return overrides

    if non_interactive:
        log.append(
            f"--non-interactive: leaving {len(resolution.unresolved)} unresolved param(s) as top-level "
            f"parameters (no local module/output could satisfy them)."
        )
        return overrides

    print("\nSome required parameters have no matching local module/output:")
    for mod_key, pname in resolution.unresolved:
        raw = input(
            f"  - {mod_key} needs '{pname}'. Enter a literal value to hardcode it, or press Enter to "
            f"leave it as a required top-level parameter: "
        ).strip()
        if raw:
            overrides[f"{mod_key}::{pname}"] = raw
            log.append(f"User supplied a hardcoded value for {mod_key}::{pname}.")
        else:
            log.append(f"Left {mod_key}::{pname} as a required top-level parameter.")
    return overrides

