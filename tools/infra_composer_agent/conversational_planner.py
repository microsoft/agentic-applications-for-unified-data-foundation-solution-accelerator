"""
Conversational resource planner -- the LLM decides EVERYTHING about which
modules to use, asking the user clarifying questions first, instead of
matching free text against a hardcoded resource-selection catalog (the old
tech_patterns.py) or a deterministic fuzzy-text matcher (the old
request_parser.py). Both of those are gone: there is no static Python
mapping from a request to a resource list anymore, and no keyword/Jaccard
scoring engine guessing at intent -- module selection is entirely driven by
the LLM reasoning over the real module catalog.

As a head start, this still tries to match the request against one of the
existing business-scenario READMEs under
001-wip-repo-structure/technical-patterns/<id>/README.md (e.g.
"chat-with-data") -- but that matching itself is done BY THE LLM reading
each README's real title/overview text (see _load_technical_patterns/
_match_pattern_with_llm), never a hardcoded id->resource-list table. When a
pattern matches, its "Resources deployed" table (business-facing names,
read live from the README on disk) is shown to the user and handed to the
planner purely as strong context to map onto real module keys -- the user
can still freely add/remove/change anything afterwards, and when nothing
matches (or the technical-patterns folder doesn't exist), this step is a
no-op and planning proceeds purely from the free-text request.

This is modeled on how microsoft/CAIRA's SKILL.md instructs a coding agent
to work: read the real reference material (here: module_index.py's scan of
the actual .bicep files on disk -- exact keys/params/outputs, never
invented), ask the user only what's needed to choose components, then
propose a plan and confirm it before generating anything. The difference
from CAIRA is that CAIRA is pure agent-instruction markdown with no code;
here the LLM still reasons over the real module catalog and drives the
question-asking/planning loop, but Python is responsible for the actual
back-and-forth I/O (input()/print()) and for validating that every module
key the LLM proposes genuinely exists in the catalog, so the LLM can never
invent a module that isn't real.

Flow (see plan_resources_conversationally):
  1. Try to match the request against an existing pattern README (LLM-
     driven, see above); if one matches, show its resource list and pass
     it as context alongside the request.
  2. Send the LLM the user's initial request (+ pattern context, if any)
     and the full real module catalog (key, category, tags, required/
     optional params, outputs -- from module_index.py, the single source
     of truth).
  3. The LLM replies with JSON: either clarifying questions (if the request
     is ambiguous/underspecified -- e.g. how many app services, whether
     private networking/RBAC/model deployments are wanted), or a final
     plan (exact module keys + counts + short reasons) once it has enough
     information.
  4. Python asks any questions via input() (skipped under --non-interactive,
     which instead tells the LLM to proceed with sensible defaults), feeds
     the answers back as the next turn, and repeats until the LLM marks
     itself "ready".
  5. Python shows the proposed plan; any free-text reply from the user
     (not just yes/no) is sent back to the SAME conversation as a revision
     request, and the loop continues until the user accepts.

Module keys are always validated against the real catalog (exact match,
then a same-category-unique suffix match) -- any key the LLM invents that
doesn't resolve is dropped with a warning, never silently kept.

The planner's own rules live in skills/resource-planning.md (an
independently editable/reviewable markdown file, matching llm_composer.py's
bicep-main-authoring.md pattern) rather than a hardcoded Python string --
see _load_skill below. That rule set also instructs the planner to
explicitly ask whether the user has EXISTING infrastructure (a VNet, Key
Vault, Log Analytics workspace, managed identity, etc.) they'd rather reuse
instead of deploying new resources -- mirroring microsoft/CAIRA's own
intake question ("Do they already have Foundry/OpenAI endpoints, hosting,
identity, observability, or frontend/API code?"). Any existing-resource
identifiers the user supplies are returned from
plan_resources_conversationally as `existing_resource_notes` and threaded
into llm_composer.py's generation prompt so the LLM can wire the literal
existing resource ID into the appropriate module parameter instead of
provisioning a new resource for that concept.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from module_index import ModuleInfo
from foundry_client import call_agent, ensure_agent

MAX_ROUNDS = 8

# Display name of the real, registered Azure AI Foundry Agent this module
# calls through (see foundry_client.ensure_agent/call_agent) -- same name
# as the pre-existing DEFAULT_PLANNER_AGENT_NAME constant this replaces,
# kept as-is (already registered/visible in the Foundry portal) even though
# it's now genuinely called by name instead of just published for
# portal-visibility. Every planner turn (including the technical-pattern-
# matching sub-step) now genuinely runs AS this agent.
PLANNER_AGENT_NAME = "infra-composer-resource-planner"

SKILLS_DIR = Path(__file__).resolve().parent / "skills"
PLANNER_SKILL_PATH = SKILLS_DIR / "resource-planning.md"

_FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)


def _strip_frontmatter(text: str) -> str:
    """Strips a leading YAML frontmatter block (--- ... ---), if present.
    See llm_composer._strip_frontmatter for why: skill files carry
    frontmatter for external discoverability only, not as LLM instruction
    content."""
    return _FRONTMATTER_RE.sub("", text, count=1).strip()


def _load_skill(path: Path = PLANNER_SKILL_PATH) -> str:
    """Loads the planner's rule set from skills/resource-planning.md -- the
    single source of truth for how the conversational planner behaves,
    kept as an independently editable/reviewable markdown file (matching
    llm_composer.py's bicep-main-authoring.md pattern) instead of a
    hardcoded Python string. Falls back to a minimal inline instruction set
    (with a clear warning marker) if the file is ever missing, so a run
    never silently loses the rules without at least surfacing it in the log."""
    if path.exists():
        return _strip_frontmatter(path.read_text(encoding="utf-8"))
    return (
        "(WARNING: resource-planning skill file not found at "
        f"{path} -- falling back to minimal inline planner instructions.)\n\n"
        "You are an infrastructure planning assistant. Given a user's request and a catalog of real "
        "Bicep modules, ask clarifying questions only when genuinely needed, then output STRICT JSON "
        "only matching: {\"ready\": bool, \"questions\": [...], \"message\": \"...\", "
        "\"plan\": [{\"module_key\": \"...\", \"count\": 1, \"reason\": \"...\"}], "
        "\"existing_resources\": [{\"concept\": \"...\", \"value\": \"...\"}]}"
    )


REPO_ROOT = Path(__file__).resolve().parents[2]
TECHNICAL_PATTERNS_DIR = REPO_ROOT / "001-wip-repo-structure" / "technical-patterns"

# Kept as a clearly-labeled EXTRA capability appended to the registered
# Planner agent's (PLANNER_AGENT_NAME) instructions (see PLANNER_INSTRUCTIONS
# below) rather than swapped in per-call. A per-call `instructions=` override
# on an agent-bound client does NOT reliably take precedence over the
# agent's own registered instructions (confirmed empirically: pattern
# matching silently stopped working once this call was converted to go
# through the agent-bound call_agent() with an `extra_instructions`
# override -- the model kept answering under the main resource-planning
# instructions instead of returning the strict JSON schema below). So this
# task is now always part of what the Planner agent knows how to do; which
# of its two jobs to run for a given call is selected via the *input*
# message instead (see _match_pattern_with_llm), since input content --
# unlike a per-call instructions override -- is always honored.
PATTERN_MATCH_INSTRUCTIONS = """You are matching a user's infrastructure request to the closest one of a \
small set of predefined technical/business patterns, each described by a title and a one-paragraph \
solution overview. You will receive the user's request and the list of pattern candidates (id, title, \
overview). Decide whether ANY of them genuinely matches the request's underlying scenario/intent \
(paraphrases count -- reason about intent, not literal keyword overlap). If none of them is a \
reasonable match, say so honestly rather than forcing a pick.

Output STRICT JSON ONLY, no markdown fences, no commentary, matching exactly this schema:
{"matched_id": "<pattern id, or null if none match>", "reason": "<one short sentence explaining the match or non-match>"}
"""

PLANNER_INSTRUCTIONS = _load_skill() + f"""

## Additional one-off sub-task: technical-pattern matching

Sometimes a single message will ask you to do a DIFFERENT, narrower job instead of the resource-planning
conversation above: classifying a user's request against a small list of predefined technical patterns.
Such a message will always start with the exact marker line "PATTERN-MATCH TASK:" -- when you see that
marker, ignore all the resource-planning instructions above for that one reply and instead follow these
rules exactly, responding with nothing but the JSON they specify:

{PATTERN_MATCH_INSTRUCTIONS}
"""


def _load_technical_patterns() -> list[dict]:
    """Reads every 001-wip-repo-structure/technical-patterns/<id>/README.md
    from disk (the on-disk file is the real source of truth -- hand edits
    are picked up automatically, no code change needed to add/edit/remove a
    pattern). Returns [{"id", "title", "overview", "resources": [(name,
    purpose), ...]}] for each pattern found; silently skips any folder
    without a README.md. This is reference material for the LLM to reason
    over -- never a hardcoded Python resource list."""
    patterns = []
    if not TECHNICAL_PATTERNS_DIR.is_dir():
        return patterns
    for pattern_dir in sorted(TECHNICAL_PATTERNS_DIR.iterdir()):
        readme_path = pattern_dir / "README.md"
        if not pattern_dir.is_dir() or not readme_path.is_file():
            continue
        text = readme_path.read_text(encoding="utf-8")

        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else pattern_dir.name

        overview_match = re.search(
            r"^##\s+Solution overview\s*\n+(.+?)(?=\n#|\Z)", text, re.MULTILINE | re.DOTALL
        )
        overview = overview_match.group(1).strip().split("\n\n")[0].strip() if overview_match else ""

        resources: list[tuple[str, str]] = []
        table_match = re.search(
            r"^##\s+Resources deployed\s*\n+(.+?)(?=\n#|\Z)", text, re.MULTILINE | re.DOTALL
        )
        if table_match:
            for line in table_match.group(1).splitlines():
                line = line.strip()
                if not line.startswith("|") or set(line.replace("|", "").strip()) <= {"-", " "}:
                    continue
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) >= 2 and cells[0].lower() != "resource":
                    resources.append((cells[0], cells[1]))

        patterns.append({"id": pattern_dir.name, "title": title, "overview": overview, "resources": resources})
    return patterns


def _match_pattern_with_llm(prompt: str, patterns: list[dict], ai_foundry_endpoint: str,
                             ai_foundry_model: str) -> tuple[dict | None, str]:
    """Asks the Planner agent which (if any) predefined pattern the request
    resembles, reasoning over each pattern's real README title/overview
    (never a hardcoded keyword table). Returns (matched pattern dict or
    None, reason). Runs through the SAME registered Planner agent
    (PLANNER_AGENT_NAME) as the
    main planning conversation (see call_agent) -- this is an internal
    sub-step of the Planner's own workflow, not a separate agent. The
    classification task is selected via the "PATTERN-MATCH TASK:" marker in
    the user message (see PLANNER_INSTRUCTIONS), not a per-call instructions
    override -- an override was tried first but does not reliably take
    precedence over an agent-bound client's own registered instructions."""
    if not patterns:
        return None, ""
    candidates = "\n".join(
        f"- id: {p['id']} | title: {p['title']} | overview: {p['overview']}" for p in patterns
    )
    messages = [
        {"role": "user", "content": (
            f"PATTERN-MATCH TASK:\nPattern candidates:\n{candidates}\n\nUser's request:\n{prompt}"
        )},
    ]
    try:
        raw = call_agent(messages, ai_foundry_endpoint, PLANNER_AGENT_NAME)
        parsed = _extract_json(raw)
    except Exception:
        return None, ""
    matched_id = parsed.get("matched_id")
    reason = str(parsed.get("reason", "") or "").strip()
    if not matched_id:
        return None, reason
    for p in patterns:
        if p["id"] == matched_id:
            return p, reason
    return None, reason


def _catalog_text(modules: list[ModuleInfo]) -> str:
    lines = []
    for m in modules:
        req = [p.name for p in m.params if p.required]
        opt = [p.name for p in m.params if not p.required]
        outs = [o.name for o in m.outputs]
        lines.append(
            f"- key: {m.key} | category: {m.category} | tags: [{', '.join(sorted(m.tags))}] | "
            f"required params: [{', '.join(req)}] | optional params: [{', '.join(opt)}] | "
            f"outputs: [{', '.join(outs)}]"
        )
    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.MULTILINE)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in planner response: {text!r}")
    return json.loads(match.group(0))


def _resolve_module_key(raw_key: str, modules_by_key: dict[str, ModuleInfo]) -> ModuleInfo | None:
    """Exact key match first; otherwise a same-suffix match IF unique (guards
    against the LLM giving a shortened/partial path instead of the exact
    catalog key) -- never a fuzzy/text-similarity guess."""
    exact = modules_by_key.get(raw_key)
    if exact is not None:
        return exact
    suffix = "/" + raw_key.lstrip("/")
    matches = [m for m in modules_by_key.values() if m.key.endswith(suffix)]
    if len(matches) == 1:
        return matches[0]
    return None


def _print_plan(plan_items: list[tuple[ModuleInfo, int, str]]) -> None:
    print("\nHere's the proposed plan:")
    for module, count, reason in plan_items:
        suffix = f" x{count}" if count > 1 else ""
        reason_txt = f" -- {reason}" if reason else ""
        print(f"  - {module.name} ({module.category}){suffix}{reason_txt}")
    print()


def plan_resources_conversationally(
    prompt: str, modules: list[ModuleInfo], ai_foundry_endpoint: str, ai_foundry_model: str,
    non_interactive: bool, log: list[str],
) -> tuple[list[ModuleInfo], dict[str, int], list[str], str | None, dict[str, str]]:
    """Runs the full ask-then-plan-then-confirm conversation and returns
    (selected_modules, requested_counts, existing_resource_notes,
    matched_pattern_id, plan_reasons). The first two are the same shapes
    agent.py's compose() previously built from the tech-pattern +
    fuzzy-matcher pipeline, so downstream code (resolver.resolve,
    copy_modules, etc.) is unaffected.
    existing_resource_notes is a new list of short "<concept>: <value>"
    strings for any existing resource identifiers the user supplied when
    asked (see skills/resource-planning.md) -- e.g. "Key Vault:
    /subscriptions/.../vaults/myKV" -- forwarded to llm_composer.py so the
    generated main.bicep can wire the literal existing resource ID instead
    of provisioning a new one for that concept.
    matched_pattern_id is the id of the technical-pattern README this
    request matched (or None if none matched/no patterns exist), and
    plan_reasons maps each planned module's key to the LLM's one-line
    reason for including it -- both are surfaced in the persisted PLAN.md
    build-plan document (see plan_doc.py) so the capability inventory is
    reviewable after the run, not just visible transiently in the console.
    Raises SystemExit if no plan could be agreed on after MAX_ROUNDS.

    Before the module-level planning conversation starts, this first tries
    to match the request against one of the existing pattern READMEs (see
    _load_technical_patterns/_match_pattern_with_llm) purely as a strong
    head-start/hint for the LLM -- if one matches, its business-facing
    resource list (from the README's own "Resources deployed" table,
    never a hardcoded catalog) is shown to the user and handed to the
    planner as context to map onto real module keys. No pattern is ever
    silently applied without being shown -- and when nothing matches
    (or there are no pattern READMEs at all), this step is a no-op and
    planning proceeds purely from the free-text request as before."""
    modules_by_key = {m.key: m for m in modules}
    catalog = _catalog_text(modules)

    # Publish/refresh the Planner agent's (PLANNER_AGENT_NAME) registered
    # instructions from the current resource-planning.md skill file BEFORE
    # any call_agent(...) use below (including the pattern-match sub-step) --
    # this is a no-op after the first call this process, so every turn in
    # this conversation runs against the same, currently-published
    # instructions.
    ensure_agent(ai_foundry_endpoint, PLANNER_AGENT_NAME, ai_foundry_model, PLANNER_INSTRUCTIONS)

    patterns = _load_technical_patterns()
    matched_pattern, match_reason = _match_pattern_with_llm(prompt, patterns, ai_foundry_endpoint, ai_foundry_model)

    pattern_context = ""
    if matched_pattern:
        resource_lines = "\n".join(f"  - {name} -- {purpose}" for name, purpose in matched_pattern["resources"])
        print(f"Based on what you described, this looks like the '{matched_pattern['id']}' pattern:")
        print(f"  {matched_pattern['title']} -- {matched_pattern['overview']}")
        print(f"\nThat pattern typically uses these resources:\n{resource_lines}\n")
        log.append(f"Matched technical pattern '{matched_pattern['id']}'" +
                    (f" ({match_reason})" if match_reason else "") + ".")
        pattern_context = (
            f"\n\nThe request appears to match the '{matched_pattern['id']}' pattern ({matched_pattern['title']}), "
            f"which typically uses these resources:\n{resource_lines}\n"
            f"Use this as a strong starting point -- map each of these business-facing resources to the best "
            f"matching real module key(s) in the catalog below, include any wiring dependency they need (managed "
            f"identity, role assignments, model deployments, etc.), and still ask about anything genuinely "
            f"ambiguous (e.g. how many app services) or any change/addition/removal the user's own request implies "
            f"on top of this baseline."
        )
    elif patterns:
        print("I couldn't find any existing technical pattern that matches this request. Could you give me "
              "more details about the infrastructure/resources you have in mind, so I can help put together "
              "the right plan?\n")
        log.append("No existing technical pattern matched this request" +
                    (f" ({match_reason})" if match_reason else "") + " -- planning purely from the prompt.")

    messages: list[dict] = [
        {"role": "user", "content": f"Module catalog:\n{catalog}\n\nUser's request:\n{prompt}{pattern_context}"},
    ]

    plan_items: list[tuple[ModuleInfo, int, str]] = []
    existing_resources: list[tuple[str, str]] = []

    for round_num in range(1, MAX_ROUNDS + 1):
        raw = call_agent(messages, ai_foundry_endpoint, PLANNER_AGENT_NAME)
        parsed = _extract_json(raw)
        messages.append({"role": "assistant", "content": raw})

        message_text = str(parsed.get("message", "") or "").strip()
        if message_text:
            log.append(f"Planner: {message_text}")

        if not parsed.get("ready", False):
            questions = [str(q).strip() for q in parsed.get("questions", []) if str(q).strip()]
            if not questions:
                # Model claims it's not ready but gave no questions -- nudge it
                # to either ask something concrete or finalize, rather than
                # looping silently forever.
                messages.append({"role": "user", "content": (
                    "You said you're not ready but didn't ask any questions. Either ask specific "
                    "questions now, or finalize the plan."
                )})
                continue
            if non_interactive:
                log.append(f"--non-interactive: answering {len(questions)} planner question(s) with defaults.")
                messages.append({"role": "user", "content": (
                    "Non-interactive mode: use sensible, safe defaults for all of these questions and "
                    "finalize your best plan now."
                )})
                continue
            print()
            if len(questions) > 1:
                print("A few quick questions before I finalize the plan:\n")
            answers = []
            for i, q in enumerate(questions, start=1):
                label = f"{i}. {q}" if len(questions) > 1 else q
                ans = input(f"{label}\n> ").strip()
                answers.append(f"Q: {q}\nA: {ans or '(no preference -- use your best judgement)'}")
                print()
            messages.append({"role": "user", "content": "\n\n".join(answers)})
            continue

        # ready == True: build/validate the plan.
        raw_plan = parsed.get("plan", [])
        plan_items = []
        for item in raw_plan:
            raw_key = str(item.get("module_key", "")).strip()
            if not raw_key:
                continue
            module = _resolve_module_key(raw_key, modules_by_key)
            if module is None:
                log.append(f"WARNING: planner proposed module_key '{raw_key}' which doesn't match any real "
                           f"module in the catalog -- dropped.")
                continue
            count = int(item.get("count", 1) or 1)
            reason = str(item.get("reason", "") or "")
            plan_items.append((module, count, reason))

        raw_existing = parsed.get("existing_resources", []) or []
        existing_resources = [
            (str(item.get("concept", "")).strip(), str(item.get("value", "")).strip())
            for item in raw_existing
            if str(item.get("concept", "")).strip() and str(item.get("value", "")).strip()
        ]
        for concept, value in existing_resources:
            log.append(f"User wants to reuse an existing {concept}: {value}")

        if not plan_items:
            messages.append({"role": "user", "content": (
                "That plan didn't resolve to any real modules from the catalog. Please propose a plan "
                "using ONLY exact module_key values copied from the catalog given earlier."
            )})
            continue

        if non_interactive:
            log.append("--non-interactive: accepting the planner's proposed plan as-is.")
            break

        _print_plan(plan_items)
        reply = input("\nShall I proceed with this? Press Enter/'yes' to continue, or describe any change:\n> ").strip()
        print()
        if reply == "" or reply.lower() in ("y", "yes"):
            log.append("User confirmed the full plan as-is.")
            break

        log.append(f"User replied to the plan confirmation with: '{reply}'")
        messages.append({"role": "user", "content": (
            f"The user reviewed your plan and replied: \"{reply}\". Revise the plan accordingly (this "
            f"may add, remove, or swap modules) and either ask a clarifying question if genuinely needed, "
            f"or finalize the revised plan."
        )})
    else:
        raise SystemExit(
            "Could not agree on a resource plan after multiple rounds of conversation. Re-run with a "
            "clearer --prompt."
        )

    selected: list[ModuleInfo] = []
    requested_counts: dict[str, int] = {}
    plan_reasons: dict[str, str] = {}
    for module, count, reason in plan_items:
        if module not in selected:
            selected.append(module)
        requested_counts[module.key] = requested_counts.get(module.key, 0) + count
        if reason:
            plan_reasons[module.key] = reason
            log.append(f"Planned '{module.key}' x{count} -- {reason}")
        else:
            log.append(f"Planned '{module.key}' x{count}")

    existing_resource_notes = [f"{concept}: {value}" for concept, value in existing_resources]
    matched_pattern_id = matched_pattern["id"] if matched_pattern else None
    return selected, requested_counts, existing_resource_notes, matched_pattern_id, plan_reasons
