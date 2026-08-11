---
title: Agentic Apps Stable Core Delta
description: Staged platform baseline delta for customer-agnostic agentic applications
author: Microsoft
ms.date: 2026-08-06
ms.topic: overview
---

## Scope

This staged Stable Core delta provides a customer-agnostic Azure platform
baseline for agentic applications. It composes with domain-independent
Technical Patterns, which receive data, prompts, labels, and business rules
from Industry Scenarios.

The delta is intended to update
`001-wip-repo-structure/stable-cores/agentic-apps` after human review. Nothing
in this staging folder has been promoted to the live Stable Core.

## Capabilities

* Azure AI Foundry account, project, model deployment, and AI Search
* Azure Storage, Cosmos DB, and optional Microsoft Fabric capacity
* Azure Container Registry and App Service hosting
* Managed identity, role assignments, monitoring, and diagnostics
* Optional private networking, private DNS, Key Vault, and administration VM
* Azure Developer CLI deployment entrypoint
* Azure Communication Services account provisioning and Event Grid delivery
* GitHub Actions OpenID Connect workload identity using immutable repository IDs
* Scoped deployment and Terraform state permissions
* Resource-group budget notifications
* Operator-confirmed phone-number acquisition tooling

## Infrastructure Options

The `infra/bicep` and `infra/terraform` folders provide side-by-side modular
deployment options. Both use local vanilla resource declarations with no Azure
Verified Modules or external module-registry references.

The Terraform flavor and the AVM-derived WAF capability conversion are
generated adaptations. They require human review, provider validation, security
review, and deployment testing before promotion or use.
