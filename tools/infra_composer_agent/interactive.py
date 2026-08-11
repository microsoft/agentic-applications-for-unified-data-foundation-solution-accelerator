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
from tech_patterns import PATTERNS as TECH_PATTERNS, suggest_patterns as suggest_tech_patterns

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


def choose_tech_pattern(prompt: str, requested_pattern: str | None, non_interactive: bool,
                         log: list[str]) -> str | None:
    """Resolves which technical pattern (see tech_patterns.py) to seed this
    composition's baseline resource list from, if any.

    `requested_pattern` is the --tech-pattern CLI value: 'none' (or falsy)
    means "don't use a pattern at all -- interpret --prompt as-is", an
    explicit catalog id always wins outright (used both for real --tech-pattern
    CLI values AND by agent.py's main() when re-passing an already-resolved
    choice back in, to avoid asking twice).

    When --tech-pattern was omitted (requested_pattern is None) and we're
    interactive, this is a real back-and-forth: it announces the best-guess
    pattern (with its name and a one-line summary) and asks the user to
    confirm, pick a different one from a short list of runner-up matches, or
    skip patterns entirely -- it never silently guesses. Under
    --non-interactive it falls back to the best-guess inference (or None)
    automatically, since there's no one to ask."""
    if requested_pattern and requested_pattern != "none":
        if requested_pattern not in TECH_PATTERNS:
            raise SystemExit(
                f"Unknown --tech-pattern '{requested_pattern}'. Choose one of: "
                f"{', '.join(TECH_PATTERNS)}, or 'none'."
            )
        log.append(f"Using technical pattern '{requested_pattern}' (from --tech-pattern).")
        return requested_pattern
    if requested_pattern == "none":
        log.append("--tech-pattern none: composing purely from --prompt, no baseline pattern used.")
        return None

    suggestions = suggest_tech_patterns(prompt, limit=3)

    if non_interactive:
        chosen = suggestions[0][0] if suggestions else None
        if chosen:
            log.append(f"--non-interactive: inferred technical pattern '{chosen}' from your description.")
        else:
            log.append("--non-interactive: no technical pattern matched your description; composing purely "
                        "from --prompt.")
        return chosen

    if not suggestions:
        print("\nI couldn't match your description to any of the predefined technical patterns.")
        return _choose_pattern_from_menu(log, header="Would you like to pick one of these instead?")

    best_id, best_score = suggestions[0]
    best_pattern = TECH_PATTERNS[best_id]
    print(f"\nBased on what you described, this looks like the '{best_id}' pattern: "
          f"{best_pattern.display_name} -- {best_pattern.summary}")
    if len(suggestions) > 1:
        others = ", ".join(f"'{pid}'" for pid, _ in suggestions[1:])
        print(f"(Other possible matches, in case that's not right: {others}.)")
    raw = input(
        f"Shall I use the '{best_id}' pattern as the starting point? [Y/n] "
        f"(n lets you pick a different one, or skip patterns entirely): "
    ).strip().lower()
    if raw in ("", "y", "yes"):
        log.append(f"Confirmed technical pattern '{best_id}' (best match for your description).")
        return best_id

    return _choose_pattern_from_menu(log, header="Which pattern would you like to follow instead?")


def _choose_pattern_from_menu(log: list[str], header: str) -> str | None:
    """Shows every catalog pattern (id, display name, one-line summary) plus
    a '0. none' option, and asks the user to pick by number. Free-text/blank/
    unrecognized input defaults to 'none' (compose purely from the prompt)."""
    print(f"\n{header}")
    keys = list(TECH_PATTERNS)
    print("  0. none -- just describe resources yourself, no predefined pattern")
    for i, pid in enumerate(keys, start=1):
        pattern = TECH_PATTERNS[pid]
        print(f"  {i}. {pid} -- {pattern.display_name}: {pattern.summary}")
    raw = input(f"Choose 0-{len(keys)} [default 0: none]: ").strip()
    if not raw or raw == "0":
        log.append("User chose no technical pattern; composing purely from the prompt.")
        return None
    try:
        chosen = keys[int(raw) - 1]
    except (ValueError, IndexError):
        print(f"Unrecognized choice '{raw}'; proceeding with no pattern.")
        log.append(f"Unrecognized pattern choice '{raw}'; composing purely from the prompt.")
        return None
    log.append(f"User selected technical pattern '{chosen}' from the menu.")
    return chosen


def confirm_pattern_plan(pattern_id: str, resources: list, source_desc: str,
                          non_interactive: bool, log: list[str],
                          excluded: list | None = None) -> bool:
    """Shows the FINAL resource plan for the chosen technical pattern --
    i.e. the pattern's README-declared baseline (tech_patterns.py's
    get_pattern_resources()) AFTER applying any exclusions/substitutions the
    user's own prompt asked for (see agent.compose()'s `_match_excludes`
    call) -- BEFORE any module is pulled from the source module library, and
    asks for explicit confirmation to proceed. Returns True to proceed,
    False to abort.

    `excluded`, when given, is the list of baseline ResourceEntry objects
    that were dropped because of something in the prompt (e.g. "no event
    grid", "postgres instead of cosmos") -- shown explicitly so the user can
    see exactly how their own wording changed the baseline plan, not just
    the pattern's raw table.

    Under --non-interactive this always proceeds (logged), since there's no
    one to confirm with -- the whole point of a scripted/CI run is that it
    completes unattended."""
    pattern = TECH_PATTERNS[pattern_id]
    print(f"\nBased on the '{pattern_id}' technical pattern ({pattern.display_name}), read from {source_desc}, "
          f"adjusted for what your prompt asked for, I'm going to create these {len(resources)} resource(s):")
    for r in resources:
        print(f"  - {r.display_name} ({r.module_key}) -- {r.purpose}")
    if excluded:
        print(f"  (dropped from the baseline pattern because your prompt asked to remove or replace them:)")
        for r in excluded:
            print(f"  - NOT included: {r.display_name} ({r.module_key})")

    if non_interactive:
        log.append(f"--non-interactive: proceeding automatically with the '{pattern_id}' pattern's "
                    f"{len(resources)} resource(s) (read from {source_desc}"
                    + (f", {len(excluded)} excluded per the prompt" if excluded else "") + ").")
        return True

    raw = input("\nShall I proceed and pull these modules from the source library? [Y/n]: ").strip().lower()
    proceed = raw in ("", "y", "yes")
    if proceed:
        log.append(f"User confirmed the '{pattern_id}' pattern's resource plan ({len(resources)} resource(s), "
                    f"read from {source_desc}"
                    + (f", {len(excluded)} excluded per the prompt" if excluded else "") + ").")
    else:
        log.append(f"User declined the '{pattern_id}' pattern's resource plan; aborting before touching "
                    f"the source module library.")
    return proceed


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
        "\nWant to add, remove, or swap anything before I generate? Describe it in plain text, "
        "or press Enter to continue with the list above: "
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
