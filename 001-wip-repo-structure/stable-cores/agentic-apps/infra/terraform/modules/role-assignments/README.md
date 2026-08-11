---
title: Role Assignments Terraform Module
description: Creates centralized workload, deployer, ACR, and Cosmos DB data-plane role assignments
author: Microsoft
ms.date: 2026-08-06
ms.topic: reference
---

## Purpose

Creates centralized workload, deployer, ACR, and Cosmos DB data-plane role assignments.

## Inputs and Outputs

Required and optional inputs are declared in `variables.tf`. Exported resource
identifiers, names, endpoints, and identities are declared in `outputs.tf`.
Sensitive values remain marked sensitive.

## Usage

The supported composition is the root `infra/terraform/main.tf` orchestrator,
which calls this module from the local path `./modules/role-assignments` and supplies all
cross-module dependencies.

## Prerequisites

* Terraform 1.6 or later
* AzureRM 4.x and AzAPI 2.x provider packages
* An authenticated principal with permission to create the module resources
* Human review and provider validation before deployment
