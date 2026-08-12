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
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from module_index import ModuleInfo
from foundry_client import call_responses

MAX_ROUNDS = 8

DEFAULT_PLANNER_AGENT_NAME = "infra-composer-resource-planner"

PLANNER_INSTRUCTIONS = """You are an infrastructure planning assistant helping a user compose an Azure \
Bicep deployment entirely out of a fixed catalog of REAL, pre-existing Bicep modules (never invent a \
module that isn't in the catalog given to you). You will receive the user's request, the full module \
catalog (each entry: key, category, tags, required/optional parameters, outputs), and the running \
conversation (any answers the user has already given to your prior questions).

Your job, each turn:
1. Decide whether you have enough information to produce a final, confident module plan. Ask \
clarifying questions ONLY when genuinely needed to avoid guessing wrong -- e.g. ambiguous counts \
("an app" -> how many app services?), missing but consequential choices the catalog offers \
(private networking/private endpoints, RBAC role assignments between resources, model deployments \
under an AI Foundry project, redundancy/scaling, diagnostic settings/monitoring). Do not ask about \
things the request already answered, and do not ask more than 1-4 questions per turn -- keep them \
short, concrete, and easy to answer.
2. Once ready, produce the final plan: the exact set of module keys (copied verbatim from the given \
catalog's "key" field) needed to satisfy the request, with a count for each and a short reason. \
Include any module a chosen resource clearly requires to function (e.g. a managed identity if a \
resource needs RBAC access to another, role-assignment modules to actually grant that access, an AI \
Foundry model deployment if an AI Foundry project was requested) -- reason about real dependencies \
like an architect would, don't just take the request's resource nouns literally.

Output STRICT JSON ONLY, no markdown fences, no commentary, matching exactly this schema:
{
  "ready": <true if you are finalizing a plan this turn, false if you still need to ask questions>,
  "questions": ["<question 1>", "<question 2>", ...],
  "message": "<one short sentence summarizing your reasoning/plan for the user>",
  "plan": [{"module_key": "<exact key from the catalog>", "count": <integer, default 1>, "reason": "<short reason>"}]
}
"questions" must be an empty list when "ready" is true. "plan" must be an empty list when "ready" is false.
Return nothing except that JSON object.
"""


REPO_ROOT = Path(__file__).resolve().parents[2]
TECHNICAL_PATTERNS_DIR = REPO_ROOT / "001-wip-repo-structure" / "technical-patterns"

PATTERN_MATCH_INSTRUCTIONS = """You are matching a user's infrastructure request to the closest one of a \
small set of predefined technical/business patterns, each described by a title and a one-paragraph \
solution overview. You will receive the user's request and the list of pattern candidates (id, title, \
overview). Decide whether ANY of them genuinely matches the request's underlying scenario/intent \
(paraphrases count -- reason about intent, not literal keyword overlap). If none of them is a \
reasonable match, say so honestly rather than forcing a pick.

Output STRICT JSON ONLY, no markdown fences, no commentary, matching exactly this schema:
{"matched_id": "<pattern id, or null if none match>", "reason": "<one short sentence explaining the match or non-match>"}
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
    """Asks the LLM which (if any) predefined pattern the request resembles,
    reasoning over each pattern's real README title/overview (never a
    hardcoded keyword table). Returns (matched pattern dict or None, reason)."""
    if not patterns:
        return None, ""
    candidates = "\n".join(
        f"- id: {p['id']} | title: {p['title']} | overview: {p['overview']}" for p in patterns
    )
    messages = [
        {"role": "system", "content": PATTERN_MATCH_INSTRUCTIONS},
        {"role": "user", "content": f"Pattern candidates:\n{candidates}\n\nUser's request:\n{prompt}"},
    ]
    try:
        raw = call_responses(messages, ai_foundry_endpoint, ai_foundry_model)
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


def plan_resources_conversationally(
    prompt: str, modules: list[ModuleInfo], ai_foundry_endpoint: str, ai_foundry_model: str,
    non_interactive: bool, log: list[str],
) -> tuple[list[ModuleInfo], dict[str, int]]:
    """Runs the full ask-then-plan-then-confirm conversation and returns
    (selected_modules, requested_counts) -- the same shapes agent.py's
    compose() previously built from the tech-pattern + fuzzy-matcher
    pipeline, so downstream code (resolver.resolve, copy_modules, etc.)
    is unaffected. Raises SystemExit if no plan could be agreed on after
    MAX_ROUNDS.

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

    patterns = _load_technical_patterns()
    matched_pattern, match_reason = _match_pattern_with_llm(prompt, patterns, ai_foundry_endpoint, ai_foundry_model)

    pattern_context = ""
    if matched_pattern:
        resource_lines = "\n".join(f"  - {name} -- {purpose}" for name, purpose in matched_pattern["resources"])
        print(f"\nBased on what you described, this looks like the '{matched_pattern['id']}' pattern: "
              f"{matched_pattern['title']} -- {matched_pattern['overview']}")
        print(f"\nThat pattern typically uses these resources:\n{resource_lines}")
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
        log.append("No existing technical pattern matched this request" +
                    (f" ({match_reason})" if match_reason else "") + " -- planning purely from the prompt.")

    messages: list[dict] = [
        {"role": "system", "content": PLANNER_INSTRUCTIONS},
        {"role": "user", "content": f"Module catalog:\n{catalog}\n\nUser's request:\n{prompt}{pattern_context}"},
    ]

    plan_items: list[tuple[ModuleInfo, int, str]] = []
    awaiting_confirmation = False

    for round_num in range(1, MAX_ROUNDS + 1):
        raw = call_responses(messages, ai_foundry_endpoint, ai_foundry_model)
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
            answers = []
            for q in questions:
                ans = input(f"{q} ").strip()
                answers.append(f"Q: {q}\nA: {ans or '(no preference -- use your best judgement)'}")
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
        reply = input("\nShall I proceed with this? Press Enter/'yes' to continue, or describe any change: ").strip()
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
    for module, count, reason in plan_items:
        if module not in selected:
            selected.append(module)
        requested_counts[module.key] = requested_counts.get(module.key, 0) + count
        if reason:
            log.append(f"Planned '{module.key}' x{count} -- {reason}")
        else:
            log.append(f"Planned '{module.key}' x{count}")

    return selected, requested_counts
