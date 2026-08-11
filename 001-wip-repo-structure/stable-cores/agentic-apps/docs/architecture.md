---
title: Agentic Apps Stable Core Architecture
description: Architecture and review boundaries for the staged platform baseline
author: Microsoft
ms.date: 2026-08-06
ms.topic: concept
---

## Platform Baseline

The core provisions shared Azure services for domain-independent agentic
applications: Azure AI Services and Foundry project wiring, AI Search, Storage,
Cosmos DB, Container Registry, App Service, Log Analytics, and Application
Insights. Optional Fabric capacity supports unified-data scenarios without
embedding industry data or prompts in the platform layer.

## Security Baseline

Managed identities and role assignments replace application secrets where the
underlying service supports them. The optional landing zone adds segmented
subnets, network security groups, private DNS zones, an RBAC-enabled Key Vault,
and Azure Bastion. Resource-specific private endpoints remain a documented gap.

## Composition

Technical Patterns consume platform endpoints and identities from this Stable
Core. Industry Scenarios provide domain data, prompts, labels, configuration,
and evaluation assets through those patterns. No domain-specific content is
included in this staged core.
