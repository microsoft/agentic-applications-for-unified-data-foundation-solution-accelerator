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
LOCAL_MODULE_RE = re.compile(r"module\s+\w+\s+'((?:\.{1,2}/)?[\w./-]+\.bicep)'")
# Native ARM resource type declarations, e.g.
# `resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {`
# -> captures "Microsoft.OperationalInsights/workspaces". These give a much
# richer/more accurate vocabulary for tag derivation than the module's own
# file name alone (see _derive_tags): a module named "log-analytics.bicep"
# never mentions the word "workspace" in its name, but its real resource
# type does -- so a request/param that says "workspace" can still match it.
ARM_RESOURCE_TYPE_RE = re.compile(r"resource\s+\w+\s+'([A-Za-z0-9.]+/[\w/]+)@[\w.-]+'")
DESCRIPTION_RE = re.compile(r"@description\('([^']*)'\)")

# CI/repo-bootstrap modules that live alongside real app-infra modules in the
# source library but are NOT resources an application deployment should ever
# provision -- they configure the CI/CD pipeline's own permissions/state, not
# anything the deployed app itself needs. Excluding them by exact file name
# keeps them out of the catalog shown to the planner entirely, so they can
# never be mistakenly selected for an unrelated app request (this was found
# via a real run where the planner picked up state-storage-permissions.bicep
# -- a module that grants CI's managed identity access to *Terraform state*
# storage -- purely because "storage"/"permissions" fuzzy-matched the
# request, then got stuck asking for a `principalId` with no real answer).
# Add to this set (by exact .bicep file name) as more CI-only modules are
# discovered, rather than trying to infer "is this CI-only" from text.
CI_BOOTSTRAP_MODULE_NAMES = {
    "ci-credentials.bicep",           # GitHub OIDC workload identity for the CI pipeline itself
    "cost-guardrail.bicep",           # resource-group budget alerts, not an app resource
    "state-storage-permissions.bicep",  # RBAC for Terraform's own state storage account
}


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

    @property
    def flat_rel_path(self) -> Path:
        """This module's path with any '<project>/infra/bicep/modules/'
        style prefix stripped down to just the segment(s) after the literal
        'modules' folder name -- see flatten_rel_path below for why. Used
        wherever the module needs to be copied/referenced in a composed
        project's OWN flat modules/ folder, as opposed to `rel_path`/`key`
        (relative to the scanned source root, used for indexing/lookup)."""
        return flatten_rel_path(self.rel_path)

    def required_params(self) -> list[ParamInfo]:
        return [p for p in self.params if p.required]


def flatten_rel_path(rel_path: Path) -> Path:
    """Strips any '<project>/infra/bicep/modules/' style prefix down to just
    the path segment(s) after the literal 'modules' folder name, so a
    composed project's own modules/ folder is a flat '<category>/<name>.bicep'
    layout instead of mirroring the source library's own nested per-project
    structure (e.g. 'agentic-apps/infra/bicep/modules/compute/app-service.bicep'
    -> 'compute/app-service.bicep'). Falls back to rel_path unchanged when no
    'modules' segment is present (e.g. the scanned root already points
    directly at a flat modules folder, so there's nothing to strip)."""
    parts = rel_path.parts
    lower_parts = [p.lower() for p in parts]
    if "modules" in lower_parts:
        idx = lower_parts.index("modules")
        remainder = parts[idx + 1:]
        if remainder:
            return Path(*remainder)
    return rel_path


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
    singularized tokens (so plural user phrasing matches singular module names).

    Acronym-aware: a boundary is only inserted where a lowercase/digit is
    immediately followed by an uppercase letter (a new word starting), or
    where a run of uppercase letters is followed by a lowercase letter (the
    acronym ending and a new Titlecase word starting) -- e.g. 'OpenAI' ->
    ['open', 'ai'], 'HTTPServer' -> ['http', 'server']. The previous naive
    rule (insert '_' before EVERY capital not at position 0) shredded
    all-caps acronyms like 'AI' into single letters ('a', 'i') which then
    get filtered out downstream as too-short noise -- silently breaking
    fuzzy matching for anything containing 'AI' (AI Search, AI Services,
    AI Foundry, ...), which is most of this project's own module catalog."""
    s = identifier.replace("-", "_")
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s)
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", s)
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


def _derive_tags(module_name: str, category: str, avm_refs: list[str], arm_resource_types: list[str] | None = None) -> set[str]:
    tags = set(_split_tokens(module_name))
    tags.add(module_name.lower())
    tags.add(category.lower())
    for ref in avm_refs:
        # e.g. avm/res/web/site:0.23.1 -> web, site
        segs = ref.split(":")[0].split("/")
        for seg in segs:
            if seg not in ("avm", "res"):
                tags.update(_split_tokens(seg))
    for res_type in arm_resource_types or []:
        # e.g. Microsoft.OperationalInsights/workspaces -> operationalinsights, workspace
        # Namespace segments are dot-separated (e.g. "Microsoft.OperationalInsights"),
        # so split on "." too and drop the "microsoft" provider prefix, otherwise
        # it leaks in as a useless "microsoft." tag fragment.
        for seg in res_type.split("/"):
            for sub in seg.split("."):
                if sub.lower() == "microsoft":
                    continue
                tags.update(_split_tokens(sub))
    return tags


def _derive_category(rel_path: Path) -> str:
    """Derives a module's category from its path relative to the scanned
    root. Two layouts are supported so the same indexer works whether
    `modules_root` points directly AT a modules folder (old layout,
    category = the first path segment, e.g. 'compute/app-service.bicep' ->
    'compute') or at a higher-level directory that contains one or more
    projects each with their own nested '.../infra/bicep/modules/<category>/'
    folder (new layout -- e.g. scanning the whole stable-cores/ directory so
    every project under it, present now or added later, is picked up
    automatically without any per-project special-casing): in that case the
    path segment immediately AFTER the literal 'modules' folder name is used
    as the category instead, so 'agentic-apps/infra/bicep/modules/compute/
    app-service.bicep' still yields 'compute', not 'agentic-apps'."""
    parts = rel_path.parts
    lower_parts = [p.lower() for p in parts]
    if "modules" in lower_parts:
        idx = lower_parts.index("modules")
        if idx + 1 < len(parts) - 1:  # category segment AND a filename after it
            return parts[idx + 1]
        return "uncategorized"  # file sits directly in .../modules/, no subfolder
    return parts[0] if len(parts) > 1 else "uncategorized"


def parse_module(path: Path, modules_root: Path) -> ModuleInfo:
    text = path.read_text(encoding="utf-8", errors="ignore")
    rel_path = path.relative_to(modules_root)
    category = _derive_category(rel_path)
    name = path.stem

    params: list[ParamInfo] = []
    for m in PARAM_RE.finditer(text):
        decorators, pname, ptype, default = m.groups()
        desc_match = DESCRIPTION_RE.search(decorators or "")
        description = desc_match.group(1) if desc_match else ""
        required = default is None and "?" not in ptype
        params.append(ParamInfo(pname, ptype, required, default, description))

    outputs: list[OutputInfo] = []
    for m in OUTPUT_RE.finditer(text):
        decorators, oname, otype = m.groups()
        desc_match = DESCRIPTION_RE.search(decorators or "")
        description = desc_match.group(1) if desc_match else ""
        outputs.append(OutputInfo(oname, otype, description))

    avm_refs = AVM_MODULE_RE.findall(text)
    arm_resource_types = ARM_RESOURCE_TYPE_RE.findall(text)
    # Resolve any locally-referenced sibling .bicep files (e.g. a helper
    # module like './cross-scope-role-assignment.bicep') to absolute paths
    # relative to this module's own folder, so they can be copied alongside
    # it even though they're never separately requested/matched as a resource.
    local_module_refs: list[Path] = []
    for rel in LOCAL_MODULE_RE.findall(text):
        candidate = (path.parent / rel).resolve()
        if candidate.exists():
            local_module_refs.append(candidate)
    tags = _derive_tags(name, category, avm_refs, arm_resource_types)

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
        if bicep_file.name in CI_BOOTSTRAP_MODULE_NAMES:
            continue
        modules.append(parse_module(bicep_file, modules_root))
    return modules
