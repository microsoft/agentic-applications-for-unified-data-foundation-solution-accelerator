"""
Dependency resolution.

Given a set of modules the user explicitly asked for, walks each module's
*required* parameters and, for any parameter that looks like a reference to
another resource (e.g. `serverFarmResourceId`, `workspaceResourceId`),
dynamically finds the best-matching module in the full index (by tag
overlap derived from the module's own file name / category / AVM
registry reference -- not a hardcoded table) and pulls it in as a
dependency. Recurses until the dependency closure is stable, guarding
against cycles.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from module_index import ModuleInfo, _split_tokens, fuzzy_overlap

CORE_PARAM_NAMES = {"solutionName", "location", "tags", "name", "enableTelemetry"}
SUFFIX_TOKENS = {"resource", "id"}
REF_SUFFIXES = ("resourceid", "id")


def is_resource_ref_param(name: str, ptype: str) -> bool:
    if name in CORE_PARAM_NAMES:
        return False
    lname = name.lower()
    if not lname.endswith(REF_SUFFIXES):
        return False
    return "string" in ptype


def normalize_concept(param_name: str) -> list[str]:
    tokens = _split_tokens(param_name)
    while tokens and tokens[-1] in SUFFIX_TOKENS:
        tokens.pop()
    return tokens


def _best_match(tokens: list[str], candidates: list[ModuleInfo], exclude_key: str) -> tuple[ModuleInfo | None, float]:
    """Jaccard similarity over tag/name tokens, used to auto-resolve a
    required parameter to whichever other selected module's output/name
    best matches it."""
    best, best_score = None, 0.0
    token_set = set(tokens)
    if not token_set:
        return None, 0.0
    for cand in candidates:
        if cand.key == exclude_key:
            continue
        overlap = fuzzy_overlap(token_set, cand.tags)
        if not overlap:
            continue
        union = token_set | cand.tags
        score = len(overlap) / len(union)
        if score > best_score:
            best, best_score = cand, score
    return best, best_score


@dataclass
class ResolutionResult:
    modules: dict[str, ModuleInfo] = field(default_factory=dict)   # key -> module, insertion order = dependency order (deps first)
    edges: dict[str, set[str]] = field(default_factory=dict)       # module.key -> set of dependency keys it needs
    explicitly_requested: set[str] = field(default_factory=set)    # keys the user directly asked for
    unresolved: list[tuple[str, str]] = field(default_factory=list)  # (module.key, param name) with no match found


def resolve(selected: list[ModuleInfo], all_modules: list[ModuleInfo]) -> ResolutionResult:
    result = ResolutionResult()
    result.explicitly_requested = {m.key for m in selected}

    queue: list[ModuleInfo] = list(selected)
    order: list[ModuleInfo] = []
    seen: set[str] = set()

    while queue:
        m = queue.pop(0)
        if m.key in seen:
            continue
        seen.add(m.key)
        deps: set[str] = set()

        for p in m.required_params():
            if not is_resource_ref_param(p.name, p.type):
                continue
            tokens = normalize_concept(p.name)
            match, score = _best_match(tokens, all_modules, exclude_key=m.key)
            if match and score > 0:
                deps.add(match.key)
                if match.key not in seen:
                    queue.append(match)
            else:
                result.unresolved.append((m.key, p.name))

        result.edges[m.key] = deps
        order.append(m)

    # Emit dependencies before dependents (simple topological pass).
    resolved_keys: list[str] = []
    module_by_key = {m.key: m for m in order}

    def visit(key: str, stack: set[str]):
        if key in resolved_keys or key in stack:
            return
        stack.add(key)
        for dep in result.edges.get(key, ()):
            visit(dep, stack)
        stack.discard(key)
        resolved_keys.append(key)

    for m in order:
        visit(m.key, set())

    result.modules = {k: module_by_key[k] for k in resolved_keys}
    return result
