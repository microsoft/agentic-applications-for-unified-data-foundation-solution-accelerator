"""
Composes the generated project: copies selected + resolved modules into a
destination folder (preserving their relative paths), then generates a
root main.bicep that declares/wires every module in dependency order,
auto-connecting parameters to upstream outputs or to shared core params
where possible, and surfacing anything it cannot resolve as a top-level
parameter instead of silently leaving a broken reference.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from module_index import ModuleInfo, fuzzy_overlap
from resolver import ResolutionResult, CORE_PARAM_NAMES, is_resource_ref_param, normalize_concept

CORE_DECLS = """@minLength(3)
@maxLength(20)
@description('A unique application/solution name used as base for all resource naming.')
param solutionName string = 'composedsolution'

@description('Primary Azure region for resource deployment.')
param location string = resourceGroup().location

@description('Tags to apply to all resources.')
param tags object = {}
"""


def _symbol_name(module: ModuleInfo, count_index: int, total_count: int) -> str:
    base = "".join(w.capitalize() for w in module.name.replace("-", "_").split("_"))
    base = base[0].lower() + base[1:]
    if total_count > 1:
        return f"{base}{count_index + 1}"
    return base


# Bicep primitive/well-known types that are always valid to reference from
# main.bicep without any import. Anything else is presumed to be a module-local
# custom `type` declaration (e.g. `subnetOutputType`, possibly `@export()`-ed)
# that main.bicep has no visibility into -- referencing it by name there is an
# undeclared-type error (BCP302), so such types must be sanitized before being
# copied into a param/output declaration in the generated orchestrator.
_PRIMITIVE_TYPE_RE = re.compile(
    r"^(string|int|bool|object|array|secureString|secureObject|resourceInput|resourceOutput|any)(\??\[\])*\??$"
)


def _safe_bicep_type(raw_type: str) -> str:
    """Returns `raw_type` unchanged if it's a Bicep primitive (optionally array/
    optional-suffixed); otherwise collapses it to the closest safe generic
    (`array` if it ends in `[]`, else `object`) so main.bicep never references
    an undeclared module-local custom type name."""
    t = raw_type.strip()
    if _PRIMITIVE_TYPE_RE.match(t):
        return t
    return "array" if t.endswith("[]") else "object"


def _find_output_match(tokens: list[str], producer: ModuleInfo):
    """Find the best output on `producer` whose name looks like a resource id."""
    candidates = [o for o in producer.outputs if o.name.lower().endswith(("id", "resourceid"))]
    if not candidates:
        candidates = producer.outputs
    for o in candidates:
        if o.name.lower() in ("resourceid", "id"):
            return o
    return candidates[0] if candidates else None


def copy_modules(resolution: ResolutionResult, source_root: Path, dest_root: Path) -> dict[str, Path]:
    """Copies each resolved module's .bicep file into dest_root/modules/<rel_path>.
    Also transitively copies any local sibling .bicep files a module
    references by relative path (e.g. 'module x './helper.bicep' = {...}')
    -- these are implementation details of that module (not separately
    selectable resources), so they're never matched/resolved as their own
    dependency, but must still be copied or the generated project will have
    dangling module references."""
    dest_modules_dir = dest_root / "modules"
    copied: dict[str, Path] = {}
    seen_local_refs: set[Path] = set()

    def copy_one(src_path: Path) -> Path:
        rel = src_path.relative_to(source_root)
        target = dest_modules_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, target)
        return target

    def copy_local_refs(refs: list[Path]) -> None:
        for ref_path in refs:
            if ref_path in seen_local_refs:
                continue
            seen_local_refs.add(ref_path)
            copy_one(ref_path)
            # A helper module can itself reference further local helpers;
            # parse it too so those are copied as well (transitive closure).
            from module_index import parse_module
            nested = parse_module(ref_path, source_root)
            copy_local_refs(nested.local_module_refs)

    for key, module in resolution.modules.items():
        target = copy_one(module.path)
        copied[key] = target
        copy_local_refs(module.local_module_refs)
    return copied


def _literal_for_type(raw: str, ptype: str) -> str:
    """Formats a user-supplied override value as a Bicep literal appropriate
    for the param's declared type -- quotes bare strings for string-typed
    params, leaves the value as-is (assumed to already be valid Bicep, e.g.
    `true`, `123`, `['a','b']`) for anything else."""
    raw = raw.strip()
    if ptype.startswith("string") and not (raw.startswith("'") or raw.startswith('"')):
        return f"'{raw}'"
    return raw


def generate_main_bicep(resolution: ResolutionResult, requested_counts: dict[str, int],
                         param_defaults: dict[str, str] | None = None) -> str:
    param_defaults = param_defaults or {}
    lines: list[str] = []
    # Collected here whenever a required resource-ref param has no in-project
    # module to satisfy it; declared as real top-level params later so the
    # generated file never references an undefined symbol.
    fallback_params: dict[str, str] = {}  # unique_param_name -> bicep type
    lines.append("// ============================================================================")
    lines.append("// main.bicep — Generated by infra_composer_agent")
    lines.append("// Composed automatically from existing AVM Bicep modules based on a natural")
    lines.append("// language infrastructure request. Do not hand-edit module wiring below;")
    lines.append("// re-run the agent instead so the composition stays reproducible.")
    lines.append("// ============================================================================")
    lines.append("targetScope = 'resourceGroup'")
    lines.append("")
    lines.append(CORE_DECLS)

    # symbol assignment: explicit multi-count modules get numbered symbols
    symbols: dict[str, list[str]] = {}
    module_symbol: dict[str, str] = {}
    for key, module in resolution.modules.items():
        count = requested_counts.get(key, 1)
        instance_symbols = []
        for i in range(count):
            sym = _symbol_name(module, i, count)
            instance_symbols.append(sym)
        symbols[key] = instance_symbols

    lines.append("// ============================================================================")
    lines.append("// Modules (dependency order: prerequisites are declared before dependents)")
    lines.append("// ============================================================================")

    for key, module in resolution.modules.items():
        count = requested_counts.get(key, 1)
        is_dependency_only = key not in resolution.explicitly_requested
        for i in range(count):
            sym = symbols[key][i]
            rel_posix = module.rel_path.as_posix()
            lines.append("")
            if is_dependency_only:
                lines.append(f"// Auto-included dependency of a requested module: {module.name}")
            lines.append(f"module {sym} './modules/{rel_posix}' = {{")
            lines.append(f"  name: take('module.{sym}', 64)")
            lines.append("  params: {")
            for p in module.params:
                if p.name in CORE_PARAM_NAMES:
                    if p.name == "name" and p.required:
                        # "name" has no default in this module (e.g. container-app),
                        # so it must always be supplied explicitly, numbered when
                        # multiple instances of the same module are requested.
                        suffix = f"-{i + 1}" if count > 1 else ""
                        lines.append(f"    name: '{module.name}{suffix}-${{solutionName}}'")
                    elif p.name in ("solutionName", "location", "tags"):
                        lines.append(f"    {p.name}: {p.name}")
                    continue
                if is_resource_ref_param(p.name, p.type):
                    tokens = normalize_concept(p.name)
                    resolved_value = None
                    for cand_key in resolution.edges.get(key, ()):
                        cand_module = resolution.modules[cand_key]
                        overlap = fuzzy_overlap(set(tokens), cand_module.tags)
                        if overlap:
                            out = _find_output_match(tokens, cand_module)
                            if out:
                                cand_sym = symbols[cand_key][0]
                                resolved_value = f"{cand_sym}.outputs.{out.name}"
                                break
                    if resolved_value:
                        lines.append(f"    {p.name}: {resolved_value}")
                    elif p.required:
                        override_key = f"{key}::{p.name}"
                        if override_key in param_defaults:
                            lines.append(f"    {p.name}: {_literal_for_type(param_defaults[override_key], p.type)} "
                                          f"// user-supplied value (no matching module found)")
                        else:
                            fallback_name = f"{sym}_{p.name}"
                            fallback_params[fallback_name] = p.type
                            lines.append(f"    {p.name}: {fallback_name} // no matching module found; declared as a top-level param")
                elif p.required:
                    # Required param with no default and not a resource reference
                    # (e.g. linuxFxVersion, containers, administrators): surface it
                    # as a top-level param instead of omitting it, which would
                    # otherwise produce an invalid/incomplete module call.
                    override_key = f"{key}::{p.name}"
                    if override_key in param_defaults:
                        lines.append(f"    {p.name}: {_literal_for_type(param_defaults[override_key], p.type)} "
                                      f"// user-supplied value")
                    else:
                        fallback_name = f"{sym}_{p.name}"
                        fallback_params[fallback_name] = p.type
                        lines.append(f"    {p.name}: {fallback_name}")
            lines.append("  }")
            lines.append("}")

    # Declare fallback top-level params for anything no local module could satisfy,
    # so the generated file is always self-consistent (no dangling references).
    if fallback_params:
        lines.append("")
        lines.append("// ============================================================================")
        lines.append("// Unresolved required parameters (no matching module found in the source repo)")
        lines.append("// ============================================================================")
        for pname, ptype in fallback_params.items():
            lines.append("@description('Required by a module; no local module produced a matching output.')")
            lines.append(f"param {pname} {_safe_bicep_type(ptype)}")
            lines.append("")

    lines.append("")
    lines.append("// ============================================================================")
    lines.append("// Outputs")
    lines.append("// ============================================================================")
    # Bicep hard-caps at 64 outputs (linter rule max-outputs). Large compositions
    # (e.g. several private-endpoint/private-dns-zone instances) can easily produce
    # far more raw outputs than that if every output of every module instance is
    # dumped verbatim, so: (1) only surface outputs for modules the user explicitly
    # asked for -- auto-included dependency modules (managed identity, private
    # endpoints, role assignments, etc.) are wiring details, not top-level results
    # the caller needs -- and (2) if that's still over the limit, keep only each
    # instance's identifying output (resourceId/id/name/endpoint) rather than every
    # field, dropping the rest instead of producing an invalid, oversized file.
    MAX_OUTPUTS = 64
    output_candidates: list[tuple[str, object]] = []  # (out_name, (sym, o))
    for key, module in resolution.modules.items():
        if key not in resolution.explicitly_requested:
            continue
        for sym in symbols[key]:
            for o in module.outputs:
                out_name = f"{sym.upper()}_{o.name.upper()}"
                output_candidates.append((out_name, (sym, o)))

    if len(output_candidates) > MAX_OUTPUTS:
        # Keep only the identifying output per (module instance) -- prefer an
        # id/resourceId-like output, else name/endpoint-like, else the first.
        by_instance: dict[str, list[tuple[str, object]]] = {}
        for out_name, (sym, o) in output_candidates:
            by_instance.setdefault(sym, []).append((out_name, (sym, o)))
        trimmed: list[tuple[str, object]] = []
        for sym, items in by_instance.items():
            def _rank(item):
                name = item[1][1].name.lower()
                if name in ("resourceid", "id"):
                    return 0
                if name.endswith(("id", "resourceid")):
                    return 1
                if name in ("name", "endpoint"):
                    return 2
                return 3
            items.sort(key=_rank)
            trimmed.append(items[0])
        output_candidates = trimmed[:MAX_OUTPUTS]

    for out_name, (sym, o) in output_candidates:
        lines.append(f"output {out_name} {_safe_bicep_type(o.type)} = {sym}.outputs.{o.name}")

    return "\n".join(lines) + "\n"
