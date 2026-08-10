"""
Generates project documentation (README.md, and optionally
docs/DeploymentGuide.md) for the composed infrastructure, following one of
two patterns modeled on real Microsoft/Azure-Samples solution accelerators:

  * "solution-accelerator" -- modeled on
    microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator:
    a README.md (solution overview, architecture, key features, quick
    deploy, prerequisites) that links out to a separate docs/DeploymentGuide.md
    with step-by-step deployment instructions.

  * "sample" -- modeled on Azure-Samples/chat-with-your-data-solution-accelerator:
    a single, simpler README.md with a Mermaid architecture diagram, "how it
    works", features, and quick deploy -- no separate deployment guide.

Content is generated generically from whatever modules were actually
resolved (names/categories/dependency edges/explicitly-requested vs.
auto-included) -- it does not hardcode per-resource-type prose, so the same
generator produces sensible docs no matter which AVM modules a given run
happens to compose.
"""
from __future__ import annotations

import re
from pathlib import Path

from resolver import ResolutionResult


def _humanize(name: str) -> str:
    return " ".join(w.capitalize() for w in re.split(r"[-_]", name) if w)


def _node_id(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", key)


def _mermaid_diagram(resolution: ResolutionResult) -> str:
    lines = ["```mermaid", "flowchart LR"]
    for key, module in resolution.modules.items():
        lines.append(f'  {_node_id(key)}["{_humanize(module.name)}"]')
    for key, deps in resolution.edges.items():
        for dep in deps:
            lines.append(f"  {_node_id(dep)} --> {_node_id(key)}")
    lines.append("```")
    return "\n".join(lines)


def _resource_table(resolution: ResolutionResult, requested_counts: dict[str, int]) -> str:
    rows = ["| Resource | Category | Count | Included because |", "|---|---|---|---|"]
    for key, module in resolution.modules.items():
        count = requested_counts.get(key, 1)
        purpose = "Explicitly requested" if key in resolution.explicitly_requested else "Auto-included dependency"
        rows.append(f"| {_humanize(module.name)} | {module.category} | {count} | {purpose} |")
    return "\n".join(rows)


def _feature_bullets(resolution: ResolutionResult) -> list[str]:
    names = {m.name.lower() for m in resolution.modules.values()}
    bullets = [
        "Composed automatically from existing, previously-reviewed AVM Bicep modules -- "
        "no infrastructure was generated from scratch.",
        "Dependencies (managed identity, monitoring, networking, etc.) are detected from each "
        "module's required parameters and included automatically -- nothing is left dangling.",
    ]
    if any("private-endpoint" in n or "private-dns" in n for n in names):
        bullets.append(
            "Private networking: private endpoints and private DNS zones are wired in for the "
            "supported data/AI services, with public network access disabled where applicable."
        )
    if any("role-assignment" in n for n in names):
        bullets.append(
            "RBAC role assignments are included so managed identities get least-privilege access "
            "to the resources they call, instead of relying on keys/connection strings."
        )
    if any("managed-identity" in n for n in names):
        bullets.append("A managed identity is provisioned and threaded through every dependent module.")
    if any("log-analytics" in n or "app-insights" in n for n in names):
        bullets.append("Centralized monitoring via Log Analytics and Application Insights.")
    if any("key-vault" in n for n in names):
        bullets.append("Secrets/certificates are backed by Key Vault rather than being embedded in code.")
    return bullets


def _quick_deploy_block(main_rel_path: str) -> str:
    return (
        "```bash\n"
        "az login\n"
        "az account set --subscription <subscription-id>\n"
        "az group create --name <resource-group-name> --location <azure-region>\n"
        "az deployment group create \\\n"
        "  --resource-group <resource-group-name> \\\n"
        f"  --template-file {main_rel_path} \\\n"
        "  --parameters solutionName=<your-solution-name> location=<azure-region>\n"
        "```"
    )


def _prereqs_table() -> str:
    return (
        "| Required permission/role | Scope | Purpose |\n"
        "|---|---|---|\n"
        "| Contributor | Subscription or resource group | Create and manage Azure resources |\n"
        "| User Access Administrator | Subscription or resource group | Assign RBAC roles to managed identities |\n"
        "| Azure CLI (`az`) 2.60+ | Local/CI environment | Deploy with `az deployment group create` |\n"
        "| Bicep CLI 0.33.0+ | Local/CI environment | Compile/validate the generated templates |"
    )


def generate_solution_accelerator_docs(
    prompt: str, resolution: ResolutionResult, requested_counts: dict[str, int],
    dest_root: Path, main_rel_path: str = "main.bicep", tech_pattern: str | None = None,
) -> list[Path]:
    """Solution-accelerator pattern: README.md + docs/DeploymentGuide.md."""
    mermaid = _mermaid_diagram(resolution)
    features = "\n".join(f"- {b}" for b in _feature_bullets(resolution))
    resource_table = _resource_table(resolution, requested_counts)
    pattern_blurb = _tech_pattern_blurb(tech_pattern)

    readme = f"""# Generated Infrastructure Composition

{prompt.strip()}
{pattern_blurb}
This project was composed automatically by `infra_composer_agent` from the natural-language request
above, by reusing existing, previously-reviewed AVM Bicep modules instead of generating infrastructure
from scratch.

<br/>

<div align="center">

[**SOLUTION OVERVIEW**](#solution-overview) | [**QUICK DEPLOY**](#quick-deploy) | [**RESOURCES INCLUDED**](#resources-included)

</div>

<br/>

## Solution overview

### Solution architecture

{mermaid}

### Key features

<details open>
<summary>Click to learn more about the key features this composition enables</summary>

{features}

</details>

### Additional resources

- [Azure Bicep documentation](https://learn.microsoft.com/azure/azure-resource-manager/bicep/)
- [Azure Verified Modules (AVM)](https://aka.ms/avm)

<br/>

## Quick deploy

Follow the step-by-step instructions in the [Deployment Guide](docs/DeploymentGuide.md), or run:

{_quick_deploy_block(main_rel_path)}

### Prerequisites and costs

{_prereqs_table()}

Pricing varies per region/usage -- use the
[Azure pricing calculator](https://azure.microsoft.com/pricing/calculator) to estimate cost for the
specific resources listed below before deploying.

<br/>

## Resources included

{resource_table}
"""

    deployment_guide = f"""# Deployment Guide

## Overview

This guide walks you through deploying this generated infrastructure composition to Azure using
`az deployment group create`. The composition was produced automatically from the request:

> {prompt.strip()}

## Step 1: Prerequisites

### 1.1 Azure account requirements

Ensure you have access to an [Azure subscription](https://azure.microsoft.com/free/) with the
following permissions:

{_prereqs_table()}

### 1.2 Service availability

Confirm the Azure region you plan to deploy to supports every resource type listed in
[Resources included](../README.md#resources-included) -- check the
[Azure Products by Region](https://azure.microsoft.com/explore/global-infrastructure/products-by-region/)
page if unsure.

## Step 2: Deploy

{_quick_deploy_block(main_rel_path)}

Any parameter that could not be automatically wired to another module's output is declared as a
required top-level parameter in `{main_rel_path}` -- pass it via `--parameters` (or the generated
`main.bicepparam` file) as shown above.

## Step 3: Verify

```bash
az deployment group show \\
  --resource-group <resource-group-name> \\
  --name <deployment-name> \\
  --query properties.outputs
```

Confirm every resource in [Resources included](../README.md#resources-included) was created and that
the outputs above resolve to the expected resource IDs/names/endpoints.
"""

    dest_root.mkdir(parents=True, exist_ok=True)
    docs_dir = dest_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    readme_path = dest_root / "README.md"
    readme_path.write_text(readme, encoding="utf-8")
    guide_path = docs_dir / "DeploymentGuide.md"
    guide_path.write_text(deployment_guide, encoding="utf-8")
    return [readme_path, guide_path]


def generate_sample_docs(
    prompt: str, resolution: ResolutionResult, requested_counts: dict[str, int],
    dest_root: Path, main_rel_path: str = "main.bicep", tech_pattern: str | None = None,
) -> list[Path]:
    """Sample pattern: a single README.md with a Mermaid diagram, no separate guide."""
    mermaid = _mermaid_diagram(resolution)
    features = "\n".join(f"- {b}" for b in _feature_bullets(resolution))
    resource_table = _resource_table(resolution, requested_counts)
    deploy_order = ", ".join(_humanize(m.name) for m in resolution.modules.values())
    pattern_blurb = _tech_pattern_blurb(tech_pattern)

    readme = f"""# Generated Infrastructure Composition

{prompt.strip()}
{pattern_blurb}
<br/>

## Solution overview

### Architecture

{mermaid}

### How it works

Resources are provisioned in dependency order so nothing references something that doesn't exist yet:
{deploy_order}. Every module was reused as-is from the existing AVM Bicep module library -- nothing here
was generated from scratch.

### Additional resources

- [Azure Bicep documentation](https://learn.microsoft.com/azure/azure-resource-manager/bicep/)
- [Azure Verified Modules (AVM)](https://aka.ms/avm)

## Features

<details open>
<summary>Click to learn more about the key features this composition enables</summary>

{features}

</details>

## Quick deploy

{_quick_deploy_block(main_rel_path)}

Any parameter that could not be automatically wired to another module's output is declared as a
required top-level parameter in `{main_rel_path}` -- pass it via `--parameters` (or the generated
`main.bicepparam` file) as shown above.

### Resources included

{resource_table}
"""

    dest_root.mkdir(parents=True, exist_ok=True)
    readme_path = dest_root / "README.md"
    readme_path.write_text(readme, encoding="utf-8")
    return [readme_path]


def _tech_pattern_blurb(tech_pattern: str | None) -> str:
    if not tech_pattern:
        return ""
    from tech_patterns import PATTERNS
    pattern = PATTERNS.get(tech_pattern)
    if not pattern:
        return ""
    return (
        f"\n> **Technical pattern:** [{pattern.display_name}]"
        f"(../../001-wip-repo-structure/technical-patterns/{pattern.id}/README.md) -- {pattern.summary}\n"
    )


def generate_docs(
    pattern: str, prompt: str, resolution: ResolutionResult, requested_counts: dict[str, int],
    dest_root: Path, main_rel_path: str = "main.bicep", tech_pattern: str | None = None,
) -> list[Path]:
    if pattern == "solution-accelerator":
        return generate_solution_accelerator_docs(prompt, resolution, requested_counts, dest_root,
                                                    main_rel_path, tech_pattern)
    if pattern == "sample":
        return generate_sample_docs(prompt, resolution, requested_counts, dest_root,
                                     main_rel_path, tech_pattern)
    raise ValueError(f"Unknown README pattern '{pattern}'. Use 'solution-accelerator' or 'sample'.")
