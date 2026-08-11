---
title: Terraform CI Credentials Module
description: Provisions secretless GitHub Actions identity and scoped Azure permissions
---

## Interface

The module creates a user-assigned managed identity and federated credential
using immutable GitHub owner and repository IDs plus an environment claim. It
grants registry push, AI inference, resource-group deployment, and Terraform
state permissions on caller-supplied scopes.
