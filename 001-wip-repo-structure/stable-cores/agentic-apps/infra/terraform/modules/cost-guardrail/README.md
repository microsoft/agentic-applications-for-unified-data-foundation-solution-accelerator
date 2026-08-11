---
title: Terraform Cost Guardrail Module
description: Adds monthly resource-group budget notifications for CI deployments
---

## Interface

The module requires a resource group, monthly amount, contact email, and start
date. It sends notifications at 80 percent actual spend and 100 percent
forecasted spend. Azure budgets notify operators but do not stop resources.
