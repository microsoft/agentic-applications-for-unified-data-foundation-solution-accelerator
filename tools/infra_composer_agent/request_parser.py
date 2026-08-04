"""
Turns a free-text infrastructure request ("2 storage accounts and 1 app
service") into a list of ResourceRequest objects, matched dynamically
against whatever modules module_index discovered -- no hardcoded module
list, no fixed folder names.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from module_index import ModuleInfo, _split_tokens, fuzzy_overlap

NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

# Split the prompt on common separators so each clause is matched independently.
CLAUSE_SPLIT_RE = re.compile(r",|\band\b|\bwith\b|\bplus\b|;|\n", re.IGNORECASE)
COUNT_RE = re.compile(
    r"^\s*(\d+|" + "|".join(NUMBER_WORDS.keys()) + r")\b", re.IGNORECASE
)
STOPWORDS = {
    "the", "for", "to", "of", "a", "an", "and", "with", "plus", "need", "needs",
    "want", "wants", "require", "requires", "please", "build", "create", "i",
    "am", "building", "new", "project", "also",
}


@dataclass
class ResourceRequest:
    text: str
    count: int
    tokens: list[str]
    matched_module: ModuleInfo | None = None
    score: float = 0.0


def _parse_count(clause: str) -> tuple[int, str]:
    m = COUNT_RE.match(clause)
    if not m:
        return 1, clause
    raw = m.group(1).lower()
    count = int(raw) if raw.isdigit() else NUMBER_WORDS[raw]
    rest = clause[m.end():]
    return count, rest


def _tokenize(clause: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9]*", clause)
    tokens: list[str] = []
    for w in words:
        tokens.extend(_split_tokens(w))
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def split_requests(prompt: str) -> list[str]:
    clauses = [c.strip() for c in CLAUSE_SPLIT_RE.split(prompt) if c.strip()]
    return clauses


def score_module(tokens: list[str], module: ModuleInfo) -> float:
    """Jaccard similarity between request tokens and module tags. Using
    Jaccard (not plain overlap-ratio) means a module whose tag set closely
    matches the request wins over a more specific module that merely
    contains all the requested tokens plus extras (e.g. 'app service' should
    match app-service, not app-service-plan)."""
    if not tokens:
        return 0.0
    token_set = set(tokens)
    overlap = fuzzy_overlap(token_set, module.tags)
    if not overlap:
        return 0.0
    union = token_set | module.tags
    return len(overlap) / len(union)


def match_requests(prompt: str, modules: list[ModuleInfo]) -> list[ResourceRequest]:
    requests: list[ResourceRequest] = []
    for clause in split_requests(prompt):
        count, rest = _parse_count(clause)
        tokens = _tokenize(rest)
        if not tokens:
            continue
        best_score = 0.0
        tied: list[ModuleInfo] = []
        for module in modules:
            s = score_module(tokens, module)
            if s > best_score:
                best_score = s
                tied = [module]
            elif s == best_score and s > 0:
                tied.append(module)
        # Genuine ties (e.g. "cosmos db" matching both the mongo- and
        # nosql-API variants equally) are broken deterministically by
        # preferring the candidate name that sorts last -- reproducible
        # and not specific to any one resource type.
        best_module = max(tied, key=lambda m: m.name) if tied else None
        req = ResourceRequest(text=clause, count=count, tokens=tokens,
                               matched_module=best_module,
                               score=best_score)
        requests.append(req)
    return requests

