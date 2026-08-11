---
title: Terraform Incoming Call Events Module
description: Connects Azure Communication Services incoming calls to an HTTPS webhook through Event Grid
---

## Interface

The module requires an Azure Communication Services resource ID and creates a
system topic. It creates the incoming-call subscription only when a webhook
endpoint is supplied. Delivery uses one event per batch and a 24-hour retry
window.
