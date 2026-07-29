# Configuration Guide — Scenario Packs

## Overview

Scenario packs are pre-built configurations that adapt the solution to a specific industry and use case. Each pack includes synthetic sample data, an ontology configuration, and curated sample questions so the solution is ready to evaluate immediately after deployment.

This guide walks you through selecting and applying a scenario pack, understanding what each pack contains, switching to a different scenario on an existing deployment, and bringing your own data.

---

## Available Scenario Packs

| Pack | Industry | Use Case | Tables | Documents |
|------|----------|----------|--------|-----------|
| **retail** | Retail | Sales analysis & product performance | 13 (account, customer, customeraccount, customerrelationshiptype, customertradename, invoice, location, orderline, orderpayment, orders, payment, product, productcategory) | 7 PDFs |
| **insurance** | Insurance | Client meeting preparation | 4 (customer, policy, claim, communicationshistory) | 7 PDFs |
| **default** | Retail | Sales analysis & product performance | Same as `retail` (used when no `--scenario` flag is provided) | Same as `retail` |

> **Note:** All sample data is synthetic and intended for demonstration and testing purposes only.

---

## Pre-requisites

Before configuring a scenario pack, complete the full solution setup described in the [Deployment Guide](./DeploymentGuide.md).

---

## Step 1: Choose a Scenario Pack

Use the `--scenario` flag when running the build script to select a pre-built scenario pack.

### Retail Scenario

```shell
python infra/scripts/post-provision/00_build_solution.py --scenario retail
```

### Insurance Scenario

```shell
python infra/scripts/post-provision/00_build_solution.py --scenario insurance
```

### Default (no flag)

If you omit `--scenario`, the `default` scenario is used automatically (equivalent to `retail`):

```shell
python infra/scripts/post-provision/00_build_solution.py
```

> Press **Enter** to start or **Ctrl+C** to cancel the process.

> **Replacing an existing scenario?** If you already have a scenario loaded and want to switch to a different one, add `--clean` to clear and recreate existing artifacts (tables, ontology, search index) before loading the new scenario data:
> ```shell
> python infra/scripts/post-provision/00_build_solution.py --scenario insurance --clean
> ```

---

## Step 2: Validate the Scenario

After the build completes, test the agent to confirm the scenario data is loaded and queries are working:

```shell
python infra/scripts/post-provision/06_test_agent.py
```

Use the sample questions below to verify each scenario.

---

## Scenario Pack Details

### Retail

**Industry:** Retail & Consumer Goods  
**Use Case:** Sales analysis and product performance  

**Sample Questions:**
See [Retail sample questions](../data/scenarios/retail/config/sample_questions.txt).

---

### Insurance

**Industry:** Financial Services / Insurance  
**Use Case:** Claims processing and customer management  

**Sample Questions:**

See [Insurance sample questions](../data/scenarios/insurance/config/sample_questions.txt).

---

## Switching to a Different Scenario on an Existing Deployment

To switch from one scenario pack to another on an already-provisioned environment, re-run the build script with the new `--scenario` flag and `--clean`. This replaces the existing scenario data and ontology configuration:

```shell
# Switch to insurance
python infra/scripts/post-provision/00_build_solution.py --scenario insurance --clean

# Switch back to retail
python infra/scripts/post-provision/00_build_solution.py --scenario retail --clean
```

> **Note:** Re-running the build from step 01 will overwrite the existing Fabric tables and agent configuration with the new scenario's data.

To re-run from a specific step without reloading data, use the `--from` flag:

```shell
# Re-run from step 03 onward (skips data upload)
python infra/scripts/post-provision/00_build_solution.py --scenario retail --from 03
```


---

## Related Documentation

| Document | Description |
|----------|-------------|
| [Deployment Guide](./DeploymentGuide.md) | Step-by-step instructions for provisioning and deploying the solution |
| [Technical Architecture](./TechnicalArchitecture.md) | System design and component overview |
| [Troubleshooting](./TroubleShootingSteps.md) | Common issues and resolution steps |
| [Customization](../data/customdata/README.md) | Customize the solution with your date | 
