"""
Interactive CLI prompts for the infra composer agent.

Keeps the agent conversational at well-defined decision points instead of
silently guessing:
  1. Which README / deployment-doc pattern to generate (see readme_gen.py).
  2. Confirming the resolved resource list and letting the user add more
     resources before anything is copied/generated.
  3. What to do about any required module parameter that has no matching
     local module/output (surfaced by resolver.py as `unresolved`) --
     hardcode a value now, or leave it as a top-level parameter.

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
    always wins outright. Otherwise: try to infer a suggestion from the
    prompt text, but ALWAYS ask interactively (never silently guess) unless
    non_interactive is set, in which case the inferred value (or a safe
    default) is used automatically."""
    if requested_pattern in README_PATTERNS:
        log.append(f"Using README pattern '{requested_pattern}' (from --readme-pattern).")
        return requested_pattern

    inferred = _infer_pattern(prompt)

    if non_interactive:
        chosen = inferred or "solution-accelerator"
        log.append(
            f"--non-interactive: selected README pattern '{chosen}'"
            + (" (inferred from prompt)" if inferred else " (default, nothing in the prompt to infer from)")
            + "."
        )
        return chosen

    print("\nWhich README / deployment-doc pattern should I generate for this project?")
    keys = list(README_PATTERNS)
    for i, key in enumerate(keys, start=1):
        suggested = "   <- suggested based on your prompt" if inferred == key else ""
        print(f"  {i}. {key} -- {README_PATTERNS[key]}{suggested}")
    default_key = inferred or "solution-accelerator"
    default_index = keys.index(default_key) + 1
    raw = input(f"Choose 1-{len(keys)} [default {default_index}: {default_key}]: ").strip()
    if not raw:
        chosen = default_key
    else:
        try:
            chosen = keys[int(raw) - 1]
        except (ValueError, IndexError):
            print(f"Unrecognized choice '{raw}'; using default '{default_key}'.")
            chosen = default_key
    log.append(f"README pattern selected interactively: '{chosen}'.")
    return chosen


def confirm_resources(resolution: ResolutionResult, requested_counts: dict[str, int],
                       non_interactive: bool, log: list[str]) -> str | None:
    """Prints the resolved resource list (explicitly requested + auto-included
    dependencies) and, unless non_interactive, asks whether to add more
    resources. Returns the user's free-text description of additions, or
    None if there's nothing more to add."""
    print("\nResolved resources for this composition:")
    for key, module in resolution.modules.items():
        count = requested_counts.get(key, 1)
        tag = "explicitly requested" if key in resolution.explicitly_requested else "auto-included dependency"
        suffix = f" x{count}" if count > 1 else ""
        print(f"  - {module.name} ({module.category}){suffix} -- {tag}")

    if non_interactive:
        log.append("--non-interactive: skipped the resource-confirmation prompt.")
        return None

    raw = input(
        "\nAdd any additional resources before generating? Describe them in plain text "
        "(e.g. '1 redis cache'), or press Enter to continue with the list above: "
    ).strip()
    if raw:
        log.append(f"User requested additional resources interactively: '{raw}'")
        return raw
    log.append("User confirmed the resource list as-is (no additions).")
    return None


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
