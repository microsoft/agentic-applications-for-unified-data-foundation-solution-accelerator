"""
Repository module scanner / indexer.

Walks a directory tree of Bicep modules and builds a structural index of
every module found: its category (derived dynamically from its folder
path, not a fixed name list), its declared parameters (with required/
optional status and default values), its outputs, and any AVM registry
module reference. This index is what the rest of the agent reasons over
instead of hardcoded folder names.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

PARAM_RE = re.compile(
    r"(?:^|\n)((?:@\w[\w()\[\]'\":,.\s\n-]*?\n)*)\s*param\s+([A-Za-z_][A-Za-z0-9_]*)\s+([\w\[\]?<>.]+)(?:\s*=\s*([^\n]+))?",
    re.MULTILINE,
)
OUTPUT_RE = re.compile(
    r"(?:^|\n)((?:@\w[\w()\[\]'\":,.\s\n-]*?\n)*)\s*output\s+([A-Za-z_][A-Za-z0-9_]*)\s+([\w\[\]?<>.]+)\s*=",
    re.MULTILINE,
)
AVM_MODULE_RE = re.compile(r"module\s+\w+\s+'br/public:(avm/[\w./:@-]+)'")
LOCAL_MODULE_RE = re.compile(r"module\s+\w+\s+'(\.{1,2}/[\w./-]+\.bicep)'")
DESCRIPTION_RE = re.compile(r"@description\('([^']*)'\)")


@dataclass
class ParamInfo:
    name: str
    type: str
    required: bool
    default: str | None
    description: str = ""


@dataclass
class OutputInfo:
    name: str
    type: str
    description: str = ""


@dataclass
class ModuleInfo:
    path: Path            # absolute path to the .bicep file
    rel_path: Path         # path relative to the scanned modules root
    category: str          # top-level folder name under modules root
    name: str               # file stem, e.g. "app-service"
    params: list[ParamInfo] = field(default_factory=list)
    outputs: list[OutputInfo] = field(default_factory=list)
    avm_refs: list[str] = field(default_factory=list)
    local_module_refs: list[Path] = field(default_factory=list)  # sibling .bicep files this module 'module ... = { ... }'-references by relative path
    tags: set[str] = field(default_factory=set)

    @property
    def key(self) -> str:
        return str(self.rel_path.as_posix())

    def required_params(self) -> list[ParamInfo]:
        return [p for p in self.params if p.required]


def _singularize(token: str) -> str:
    """Very small naive plural stripper so 'accounts' matches 'account', etc."""
    if len(token) > 3 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("es") and token[-3] in "sxz":
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _split_tokens(identifier: str) -> list[str]:
    """Split a camelCase / kebab-case / snake_case identifier into lowercase,
    singularized tokens (so plural user phrasing matches singular module names)."""
    s = identifier.replace("-", "_")
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", s)
    return [_singularize(t.lower()) for t in s.split("_") if t]


def fuzzy_overlap(token_set: set[str], tag_set: set[str]) -> set[str]:
    """Overlap between two token sets, also counting compound-word matches
    (e.g. request token 'server'/'farm' against a module tag 'serverfarm'
    derived from an AVM registry path segment that has no separators)."""
    overlap: set[str] = token_set & tag_set
    for t in token_set:
        if t in overlap or len(t) < 4:
            continue
        for tag in tag_set:
            if len(tag) >= 4 and (t in tag or tag in t):
                overlap.add(t)
                break
    return overlap


def _derive_tags(module_name: str, category: str, avm_refs: list[str]) -> set[str]:
    tags = set(_split_tokens(module_name))
    tags.add(module_name.lower())
    tags.add(category.lower())
    for ref in avm_refs:
        # e.g. avm/res/web/site:0.23.1 -> web, site
        segs = ref.split(":")[0].split("/")
        for seg in segs:
            if seg not in ("avm", "res"):
                tags.update(_split_tokens(seg))
    return tags


def parse_module(path: Path, modules_root: Path) -> ModuleInfo:
    text = path.read_text(encoding="utf-8", errors="ignore")
    rel_path = path.relative_to(modules_root)
    category = rel_path.parts[0] if len(rel_path.parts) > 1 else "uncategorized"
    name = path.stem

    params: list[ParamInfo] = []
    for m in PARAM_RE.finditer(text):
        decorators, pname, ptype, default = m.groups()
        desc_match = DESCRIPTION_RE.search(decorators or "")
        description = desc_match.group(1) if desc_match else ""
        is_optional_type = ptype.rstrip().endswith("?") or ptype.rstrip().endswith("]")
        required = default is None and "?" not in ptype
        params.append(ParamInfo(pname, ptype, required, default, description))

    outputs: list[OutputInfo] = []
    for m in OUTPUT_RE.finditer(text):
        decorators, oname, otype = m.groups()
        desc_match = DESCRIPTION_RE.search(decorators or "")
        description = desc_match.group(1) if desc_match else ""
        outputs.append(OutputInfo(oname, otype, description))

    avm_refs = AVM_MODULE_RE.findall(text)
    # Resolve any locally-referenced sibling .bicep files (e.g. a helper
    # module like './cross-scope-role-assignment.bicep') to absolute paths
    # relative to this module's own folder, so they can be copied alongside
    # it even though they're never separately requested/matched as a resource.
    local_module_refs: list[Path] = []
    for rel in LOCAL_MODULE_RE.findall(text):
        candidate = (path.parent / rel).resolve()
        if candidate.exists():
            local_module_refs.append(candidate)
    tags = _derive_tags(name, category, avm_refs)

    return ModuleInfo(
        path=path,
        rel_path=rel_path,
        category=category,
        name=name,
        params=params,
        outputs=outputs,
        avm_refs=avm_refs,
        local_module_refs=local_module_refs,
        tags=tags,
    )


def build_index(modules_root: Path) -> list[ModuleInfo]:
    modules = []
    for bicep_file in sorted(modules_root.rglob("*.bicep")):
        if bicep_file.name in ("main.bicep",):
            continue
        modules.append(parse_module(bicep_file, modules_root))
    return modules
