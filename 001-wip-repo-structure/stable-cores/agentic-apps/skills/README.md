---
title: Agentic Apps Telephony Setup
description: Operational tooling for acquiring an Azure Communication Services phone number
---

## Phone Number Setup

Install `azure-communication-phonenumbers` and `azure-identity`, authenticate
with Azure, then pass the Azure Communication Services endpoint to the script.
The operator must confirm the displayed recurring charge unless
`--auto-approve` is supplied.

```bash
python phone-number-setup.py \
  --endpoint https://<name>.communication.azure.com \
  --country US \
  --type toll-free
```
