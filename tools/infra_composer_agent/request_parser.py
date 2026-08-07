"""
Shared token/score utilities for matching a free-text resource description
against whatever modules module_index discovered -- no hardcoded module
list, no fixed folder names.

The only consumer of these utilities is llm_interpreter.py: the LLM (via
the persistent Azure AI Foundry interpreter agent) identifies WHICH
resource concepts are being requested, and this module's `_tokenize`/
`score_module` fuzzy-match each concept against the real module catalog so
the agent never has to invent a module path. There is no standalone
deterministic "parse the whole prompt without an LLM" path any more --
AI Foundry is the only interpretation backend.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from module_index import ModuleInfo, _split_tokens, fuzzy_overlap

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


def _tokenize(clause: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9]*", clause)
    tokens: list[str] = []
    for w in words:
        tokens.extend(_split_tokens(w))
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


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
