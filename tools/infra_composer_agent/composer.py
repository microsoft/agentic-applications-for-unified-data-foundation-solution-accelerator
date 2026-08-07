"""
Copies selected + resolved modules into a destination folder, preserving
their relative paths.

Authoring the root main.bicep itself is done entirely by the LLM (see
llm_composer.py) via the persistent Azure AI Foundry author agent -- there
is no deterministic/static template generator here. That keeps exactly one
code path for main.bicep authoring instead of a static generator plus an
LLM path, and it means output quality (feature flags, conditionals, output
wiring) is always the architect-style LLM output, never a flat fallback.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from resolver import ResolutionResult


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
