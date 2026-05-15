# Agentic Applications for Unified Data Foundation — Development Plan

Repo: `microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator`  
Last updated: 2026-05-14

---

## 1. Pillars

| Pillar | Description |
|--------|-------------|
| **Stable Core** | `azd up` provisions all Azure resources and Fabric capacity as part of the baseline. No manual portal steps required. |
| **Config (Scenario Packs)** | Parameterized deployments driven by scenario packs aligned to current use cases. Scripts accept a `--scenario-pack` argument to build the solution dynamically. |
| **Customization (BYOD)** | Bring-your-own-data path using the existing upload + run-scripts pattern. Focus is on documentation: data structure, ingestion steps, and validation guidance. |
| **Deploy with AVM** | An Azure Verified Modules (AVM)-based deployment path with security controls, compliance considerations, and standardized provisioning. |

---

## 2. Stable Core

**Goal:** `azd up` provisions all Azure resources **and** Fabric capacity as part of the baseline deployment. No manual portal steps required.

| Task | Description | Files | Status |
|------|-------------|-------|--------|
| Keep `azd up` flow | Preserve the existing end-to-end `azd up` provisioning flow for all Azure resources (AI Foundry, AI Search, App Service, Cosmos DB, SQL, Container Registry). | `infra/main.bicep`, `azure.yaml` | ✅ |
| Add Fabric capacity to baseline | Add a Fabric capacity Bicep module (`deploy_fabric_capacity.bicep`) provisioned inline during `azd up`. Gate behind a `deployFabricCapacity bool` param so users with an existing capacity can opt out. Default SKU: F2. | `infra/deploy_fabric_capacity.bicep`, `infra/main.bicep` | ☐ |
| Wire deployment params and outputs | `DEPLOY_FABRIC_CAPACITY` is set as an azd environment variable (`azd env set DEPLOY_FABRIC_CAPACITY false`) and bound in `main.parameters.json`. `FABRIC_CAPACITY_ADMIN_MEMBERS` requires no user input; it auto-populates from `deployer().userPrincipalName` in Bicep. `FABRIC_CAPACITY_NAME` is a Bicep **output** that azd writes into the generated `.azure/<env>/.env` after deployment — downstream scripts read it from there. | `infra/main.bicep`, `infra/main.parameters.json` | ☐ |
| Validate end-to-end | Confirm `azd up` completes with Fabric capacity provisioned and a baseline scenario runs without any manual portal steps. Update `documents/DeploymentGuide.md`. | `documents/DeploymentGuide.md` | ☐ |

**Exit criteria:**
- `azd up` completes with Fabric capacity fully provisioned alongside all other Azure resources.
- Users with an existing capacity set `DEPLOY_FABRIC_CAPACITY=false` to skip creation.
- `documents/DeploymentGuide.md` no longer lists manual Fabric portal steps as a prerequisite.

---

## 3. Config (Scenario Packs)

**Goal:** Support parameterized deployments using pre-built scenario packs aligned to current use cases (`Retail-sales-analysis`, `Insurance-improve-customer-meetings`). A single `--scenario-pack` CLI flag selects data, industry, use case, and agent configuration without any `.env` editing.

| Task | Description | Files | Status |
|------|-------------|-------|--------|
| Author Retail scenario pack | Pre-built data pack for `Retail-sales-analysis`: customers, products, transactions, stores (CSV), retail policy + product catalog (PDF), `ontology_config.json`, `sample_questions.txt`. | `data/scenarios/retail/` | ☐ |
| Author Insurance scenario pack | Pre-built data pack for `Insurance-improve-customer-meetings`: policies, claims, customers, agents (CSV), claims process + underwriting guidelines (PDF), `ontology_config.json`, `sample_questions.txt`. | `data/scenarios/insurance/` | ☐ |
| Migrate `data/default` to scenario pack structure | Move the existing `data/default/` content into `data/scenarios/<pack-name>/` so it matches the canonical folder layout (`config/`, `tables/`, `documents/`). Update all script references from `data/default` to the new path. Remove `_generated_script.py` from the migrated folder — it is a generation artifact and does not belong in a checked-in scenario pack. | `data/scenarios/`, `data/default/`, `scripts/.env.example` | ☐ |
| Add scenario registry | `scripts/scenarios.py` — authoritative mapping of pack names to folder paths, use case values, and descriptions. `00_build_solution.py` validates `--scenario-pack` against this registry. | `scripts/scenarios.py` | ☐ |
| Update scripts for `--scenario-pack` | `scripts/00_build_solution.py` accepts `--scenario-pack <name>`, resolves the data folder, sets `INDUSTRY` and `USECASE`, skips AI generation for pre-built packs, and passes `--data-folder` explicitly to each child script. | `scripts/00_build_solution.py` | ☐ |
| Add `--list-scenarios` flag | `python scripts/00_build_solution.py --list-scenarios` prints all available packs with descriptions and exits 0. No Azure calls or `.env` required. | `scripts/00_build_solution.py`, `scripts/scenarios.py` | ☐ |
| Remove `usecase` from Bicep; move landing text to Python | Remove the `usecase` param from `main.bicep` entirely — scenario identity is owned by the scenario registry, not the infra layer. Move the `CHAT_LANDING_TEXT` app setting out of `deploy_frontend_docker.bicep` and into `scripts/08_app_deployment.py`, which reads the landing text from the active scenario pack and updates the app setting post-deployment. | `infra/main.bicep`, `scripts/08_app_deployment.py`, `scripts/scenarios.py` | ☐ |

**Exit criteria:**
- `python scripts/00_build_solution.py --scenario-pack retail` and `--scenario-pack insurance` run end-to-end without any `.env` modification.
- `--list-scenarios` lists all available packs.
- Backward compatibility: users who set `DATA_FOLDER` in `.env` are unaffected.

---

## 4. Customization (BYOD)

**Goal:** The core BYO-data pattern (place CSVs + PDFs in `data/customdata/`, run scripts) is functional. This pillar focuses on documentation — data structure requirements, ingestion steps, and validation guidance — so any user can follow the guide and get a working agent from their own data.

| Task | Description | Files | Status |
|------|-------------|-------|--------|
| Document data structure | Update `data/customdata/README.md` with required folder layout, CSV format requirements (header row, UTF-8, minimum 2 columns), and PDF placement guidance. | `data/customdata/README.md` | ☐ |
| Document ingestion steps | Add a step-by-step quick start covering the exact commands for both Azure-only and Fabric modes, including required CLI arguments. | `data/customdata/README.md` | ☐ |
| Document validation guidance | Add a troubleshooting section: common errors (empty `tables/` folder, encoding issues, missing `--industry`/`--usecase`, Fabric workspace not found) with actionable fixes. | `data/customdata/README.md` | ☐ |
| Add input validation | Validate that `tables/*.csv` exists before any Azure API call; warn if `documents/` is empty; emit a warning when `FABRIC_WORKSPACE_ID` is set but the Fabric step will be skipped. | `scripts/00_build_solution.py`, `scripts/generate_config_from_csv.py` | ☐ |

**Exit criteria:**
- A user with no prior knowledge can follow `data/customdata/README.md` alone and get a working agent from their own data.
- `python scripts/00_build_solution.py --custom-data data/customdata --industry "<industry>" --usecase "<usecase>"` runs end-to-end in both Azure-only and Fabric modes.
- Both modes are validated and documented in `data/customdata/README.md`.

---

## 5. Deploy with AVM

**Goal:** Provide an AVM-based deployment path as an alternative to the default Bicep modules. The AVM path enforces security controls, addresses compliance considerations, and uses standardized provisioning patterns consistent with the Azure Verified Modules library.

| Task | Description | Files | Status |
|------|-------------|-------|--------|
| Identify AVM modules | Identify applicable Azure Verified Modules for each provisioned resource type: AI Foundry, App Service, Cosmos DB, SQL, Container Registry, Fabric capacity. | `infra/avm/` | ☐ |
| Author AVM Bicep templates | Create AVM-based Bicep templates under `infra/avm/` as a drop-in alternative to the existing `infra/deploy_*.bicep` modules. | `infra/avm/` | ☐ |
| Apply security controls | Enforce private endpoints, managed identity authentication, RBAC least-privilege assignments, and Key Vault integration across all AVM modules. | `infra/avm/` | ☐ |
| Apply compliance settings | Add resource locks, diagnostic settings, audit logging, and tagging policies aligned to common compliance frameworks. | `infra/avm/` | ☐ |
| Standardized provisioning | Enforce consistent naming conventions, SKU defaults, and region constraints across all AVM modules. | `infra/avm/` | ☐ |
| Document AVM deployment path | Add an AVM deployment section to `documents/DeploymentGuide.md` covering prerequisites, parameter differences from the default path, and security configuration options. | `documents/DeploymentGuide.md` | ☐ |

**Exit criteria:**
- `azd up` with an AVM-targeted parameter (e.g., `DEPLOY_WITH_AVM=true`) provisions all resources using AVM modules.
- Private endpoints, managed identity, RBAC, and Key Vault integration are active by default in the AVM path.
- Resource locks, diagnostics, audit logs, and tags are applied automatically.
- `documents/DeploymentGuide.md` covers the AVM path end-to-end.
