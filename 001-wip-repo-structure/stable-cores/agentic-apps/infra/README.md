---
title: Agentic Apps Infrastructure Delta
description: Deployment options and validation status for the staged agentic apps Stable Core
author: Microsoft
ms.date: 2026-08-06
ms.topic: how-to
---

## Deployment Options

The staged core provides two local, modular infrastructure options:

* `bicep/main.bicep` calls reusable modules under `bicep/modules`
* `terraform/main.tf` calls reusable modules under `terraform/modules`

Neither option uses Azure Verified Modules or external infrastructure module
registries. Terraform provider packages are runtime dependencies, not remote
infrastructure modules.

## Capability Parity

| Capability | Bicep | Terraform |
|---|---|---|
| Foundry account and project creation or reuse | Yes | Yes |
| GPT and embedding model deployments | Yes | Yes |
| Search, Storage, and Application Insights project connections | Yes | Yes |
| Fabric capacity creation or reuse | Yes | Yes |
| Search, Storage, Cosmos DB, Foundry, and ACR RBAC | Yes | Yes |
| Existing Log Analytics workspace reuse | Yes | Yes |
| Python or .NET backend selection | Yes | Yes |
| WAF landing-zone network, DNS, Key Vault, Bastion, and diagnostics | Yes | Yes |
| Private endpoints for platform services | DNS and subnet baseline | Yes |
| Azure Communication Services and incoming-call events | Yes | Yes |
| GitHub Actions OIDC workload identity | Yes | Yes |
| Resource-group budget notifications | Yes | Yes |

The Terraform flavor uses AzAPI only where AzureRM does not expose the required
Foundry project, connection, Fabric capacity, or Cosmos DB data-plane resource.
All infrastructure modules remain local to this staged core.

## Contact Center Infrastructure

Both entrypoints add Azure Communication Services, incoming-call Event Grid
delivery, GitHub Actions OIDC federation, scoped deployment and state
permissions, and monthly budget notifications. CI resources are disabled by
default and require immutable repository IDs, a state storage account, and a
budget contact when enabled.

The Bicep contact-center modules were generated from the provided Terraform and
require human security and deployment validation. Webhook endpoints must use
HTTPS and should validate incoming Event Grid events.
## Bicep Status

The Bicep baseline comes from the contribution's vanilla implementation. The
`networking/landing-zone.bicep` module is a generated vanilla conversion of
approved AVM-based WAF capabilities. It is opt-in through
`enablePrivateNetworking` and requires human security and deployment review.

Run a syntax and module-resolution check with:

```powershell
az bicep build --file infra/bicep/main.bicep
```

## Terraform Status

> [!WARNING]
> The Terraform flavor was generated from the provided Bicep. Human-review and
> validate it before deployment.

Initialize and validate without applying resources:

```powershell
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform plan
```

## WAF Decisions

* Reliability: zone-redundant storage and modular service boundaries
* Security: managed identities, disabled local authentication where supported,
  TLS 1.2, private containers, centralized RBAC, Key Vault, NSGs, private DNS,
  Bastion, and optional private endpoints
* Cost optimization: Basic App Service and Search defaults with explicit sizing
* Operational excellence: Log Analytics, Application Insights, VNet metrics,
  and explicit module contracts
* Performance efficiency: independently sized compute, search, storage, AI,
  model deployment, and Fabric resources

## Remaining Limitations

* Terraform CLI and provider plugins are unavailable in the current environment,
  so provider-schema validation, formatting, planning, and deployment remain
  pending
* No Azure subscription deployment, what-if, plan, or cost validation was run
* Private endpoints are created when enabled, but public network access remains
  enabled for workload services to preserve the staged Bicep deployment behavior;
  disabling public access requires an approved application routing change
* Existing Foundry projects in another subscription require an explicitly aliased
  provider configured for that subscription before Terraform can manage
  cross-subscription connections and role assignments
* Fabric workspace creation remains a post-provision operation; both IaC flavors
  provision or reuse the Fabric capacity only
