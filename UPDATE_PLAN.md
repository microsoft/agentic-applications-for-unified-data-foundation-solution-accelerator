# Update Plan — Implementation Details

This document expands each pillar in `DEVELOPMENT_PLAN.md` into specific, actionable implementation steps.

---

## 1. Stable Core

### Keep the current `azd up` flow

No changes to the existing `azd up` provisioning flow. All current Azure resources (AI Foundry, AI Search, App Service, Cosmos DB, SQL, Container Registry) continue to be provisioned exactly as they are today. The goal is additive: layer Fabric capacity creation on top without breaking or restructuring what works.

---

### Add Fabric capacity creation to the baseline

**What it is:** `azd up` currently does not create a Microsoft Fabric capacity. Users must open the Fabric portal, create an F2+ capacity manually, then return to the terminal — breaking the one-command deploy experience.

**Implementation steps:**

1. Create `infra/deploy_fabric_capacity.bicep`:
   ```bicep
   param capacityName string
   param location string = resourceGroup().location
   param adminMembers array
   param sku object = { name: 'F2', tier: 'Fabric' }

   resource fabricCapacity 'Microsoft.Fabric/capacities@2023-11-01' = {
     name: capacityName
     location: location
     sku: sku
     properties: {
       administration: {
         members: adminMembers
       }
     }
   }

   output capacityId string = fabricCapacity.id
   output capacityName string = fabricCapacity.name
   ```

2. In `infra/main.bicep`:
   - Add `param deployFabricCapacity bool = true`
   - Add `param fabricCapacityAdminMembers array` with a default that auto-populates from the deploying user — no user input required:
     ```bicep
     param fabricCapacityAdminMembers array = contains(deployer(), 'userPrincipalName')
         ? [deployer().userPrincipalName]
         : []
     ```
   - Add a conditional module call: `module fabricCapacity 'deploy_fabric_capacity.bicep' = if (deployFabricCapacity) { ... }`
   - Add a Bicep **output** so azd writes the capacity name into the generated `.azure/<env>/.env` automatically after deployment:
     ```bicep
     output FABRIC_CAPACITY_NAME string = deployFabricCapacity ? fabricCapacity.outputs.capacityName : ''
     ```
     Downstream Python scripts read `FABRIC_CAPACITY_NAME` from the generated `.env` — no manual copy-paste.

3. In `infra/main.parameters.json`:
   - Bind `deployFabricCapacity` to `${DEPLOY_FABRIC_CAPACITY}`. Users who already have a Fabric capacity run `azd env set DEPLOY_FABRIC_CAPACITY false` before `azd up`.
   - Do **not** bind `fabricCapacityAdminMembers` — the Bicep default (`deployer().userPrincipalName`) handles it entirely at deploy time.

4. The flow for these variables is:
   - **Input:** `DEPLOY_FABRIC_CAPACITY` set via `azd env set` (defaults to `true` in `main.parameters.json`)
   - **Output:** `FABRIC_CAPACITY_NAME` written to `.azure/<env>/.env` by azd post-deployment
   - **Auto-resolved:** `FABRIC_CAPACITY_ADMIN_MEMBERS` derived from `deployer()` at deploy time

5. Update `documents/DeploymentGuide.md`:
   - Remove the manual "create a Fabric capacity in the portal" prerequisite step
   - Document `azd env set DEPLOY_FABRIC_CAPACITY false` as the opt-out for users with an existing capacity

**Done when:** `azd up` with default parameters provisions a Fabric capacity in the resource group. Setting `DEPLOY_FABRIC_CAPACITY=false` skips creation and all other resources still provision successfully.

---

## 2. Config (Scenario Packs)

### Add support for parameterized deployments using scenario packs

**What it is:** `infra/main.bicep` already declares `Retail-sales-analysis` and `Insurance-improve-customer-meetings` as `usecase` values, but no matching data packs exist under `data/`. Scripts currently require manual `.env` edits to switch between scenarios.

**Scenario pack structure** (consistent across all packs):
```
data/scenarios/<pack-name>/
├── config/
│   ├── ontology_config.json
│   ├── sample_questions.txt
│   └── schema_prompt.txt
├── tables/
│   └── *.csv
└── documents/
    └── *.pdf
```

**Migrating `data/default` to the scenario pack structure:**

The existing `data/default/` folder already has the right sub-structure (`config/`, `tables/`, `documents/`) but lives at the wrong path and contains a generation artifact (`_generated_script.py`) that should not be part of a checked-in pack.

1. Create `data/scenarios/<pack-name>/` (the appropriate name for the existing default data).
2. Move `config/`, `tables/`, and `documents/` into the new folder.
3. Do **not** carry over `_generated_script.py` — it is a one-time generation output, not a pack asset.
4. Find and update all references to `data/default` across scripts, `.env.example`, and any documentation.
5. Add the migrated pack to `SCENARIO_REGISTRY` in `scripts/scenarios.py`.

**Retail pack** (`data/scenarios/retail/`):
- Tables: `customers.csv`, `products.csv`, `transactions.csv`, `stores.csv` (200–500 rows each, referentially consistent)
- Documents: `retail_policy.pdf`, `product_catalog.pdf`
- `ontology_config.json`: entities `Customer`, `Product`, `Transaction`, `Store`; `usecase` key set to `Retail-sales-analysis`

**Insurance pack** (`data/scenarios/insurance/`):
- Tables: `policies.csv`, `claims.csv`, `customers.csv`, `agents.csv`
- Documents: `claims_process.pdf`, `underwriting_guidelines.pdf`
- `ontology_config.json`: entities `Customer`, `Policy`, `Claim`, `Agent`; `usecase` key set to `Insurance-improve-customer-meetings`

**Scenario registry** — new file `scripts/scenarios.py`:
```python
SCENARIO_REGISTRY = {
    "retail": {
        "folder": "data/scenarios/retail",
        "usecase": "Retail-sales-analysis",
        "description": "Retail: customers, products, transactions, and stores",
    },
    "insurance": {
        "folder": "data/scenarios/insurance",
        "usecase": "Insurance-improve-customer-meetings",
        "description": "Insurance: policies, claims, customers, and agents",
    },
}

def get_scenario(name: str) -> dict:
    if name not in SCENARIO_REGISTRY:
        valid = ", ".join(SCENARIO_REGISTRY.keys())
        raise ValueError(f"Unknown scenario pack '{name}'. Valid options: {valid}")
    return SCENARIO_REGISTRY[name]
```

**`main.bicep` alignment:** Replace the `@allowed([...])` decorator on `usecase` with a `@description` listing valid values. Registry-level validation in `scenarios.py` removes the need for Bicep-level enforcement.

---

### Remove `usecase` from Bicep and move landing text to Python

**What it is:** The `usecase` param in `main.bicep` currently does two things: drives a hard-coded `landingText` ternary and is emitted as a `USE_CASE` output. Both responsibilities belong in Python now that the scenario registry owns use case identity. This change makes Bicep scenario-agnostic.

**Changes to `infra/main.bicep`:**
1. Remove the `usecase` param and its `@allowed` / `@description` decorators entirely.
2. Remove the `landingText` var and the `CHAT_LANDING_TEXT` entry from the frontend app settings block in `deploy_frontend_docker.bicep`.
3. Remove the `USE_CASE` output.

**Changes to `scripts/scenarios.py`:**
Add a `landing_text` key to each registry entry:
```python
SCENARIO_REGISTRY = {
    "retail": {
        "folder": "data/scenarios/retail",
        "usecase": "Retail-sales-analysis",
        "landing_text": "You can ask questions around sales, products and orders.",
        "description": "Retail: customers, products, transactions, and stores",
    },
    "insurance": {
        "folder": "data/scenarios/insurance",
        "usecase": "Insurance-improve-customer-meetings",
        "landing_text": "You can ask questions around customer policies, claims and communications.",
        "description": "Insurance: policies, claims, customers, and agents",
    },
}
```

**Changes to `scripts/08_app_deployment.py`:**
1. Accept the resolved scenario pack (passed from `00_build_solution.py` via `--scenario-pack`).
2. Look up `landing_text` from the registry for the active pack.
3. Update the frontend app service's `CHAT_LANDING_TEXT` app setting via the Azure SDK or CLI after deployment.

**Done when:** `main.bicep` has no `usecase` param; the frontend displays the correct landing text for each scenario pack driven entirely by `08_app_deployment.py`.

---

### Update scripts to take a scenario pack input and build the solution dynamically

**What it is:** `scripts/00_build_solution.py` has no scenario selector. Users must manually edit `DATA_FOLDER` in `.env`. A `--scenario-pack` argument resolves the data folder, sets `INDUSTRY` and `USECASE`, and routes the full pipeline — no `.env` edits required.

**`00_build_solution.py` changes:**

1. Add `--scenario-pack <name>` argument (mutually exclusive with `--custom-data`):
   ```python
   parser.add_argument('--scenario-pack', metavar='NAME',
       help='Pre-built scenario pack to deploy. Valid values: retail, insurance')
   ```

2. When `--scenario-pack` is provided:
   - Call `scenarios.get_scenario(args.scenario_pack)` — raises `ValueError` for unknown names
   - Set `DATA_FOLDER = pack["folder"]` for this run only (do not write to `.env`)
   - Set `INDUSTRY` and `USECASE` from pack metadata
   - Skip step 01 (`01_generate_data.py`) — pre-built packs do not need AI generation
   - Log: `Using scenario pack: retail → data/scenarios/retail`

3. Pass `--data-folder <resolved_path>` explicitly to each child script (`03_generate_agent_prompt.py`, `05_upload_to_search.py`, `06_create_agent.py`) so the active pack overrides any stale `DATA_FOLDER` in `.env`.

4. Add `--list-scenarios` flag:
   ```
   $ python scripts/00_build_solution.py --list-scenarios

   Available scenario packs:
     retail     Retail: customers, products, transactions, and stores
     insurance  Insurance: policies, claims, customers, and agents
   ```
   Prints the registry and exits 0. No Azure calls or `.env` required.

**Child script changes** (each of `03_generate_agent_prompt.py`, `05_upload_to_search.py`, `06_create_agent.py`):
```python
parser.add_argument('--data-folder', default=None,
    help='Path to the data folder. Overrides DATA_FOLDER env var when provided.')
```
Resolve priority: `--data-folder` CLI arg → `DATA_FOLDER` env var → script default.

**Done when:** `python scripts/00_build_solution.py --scenario-pack retail` and `--scenario-pack insurance` both run end-to-end without any `.env` modification. Users who rely on `DATA_FOLDER` in `.env` are unaffected.

---

## 3. Customization (BYOD)

### Document data structure, ingestion steps, and validation guidance

**What it is:** The core BYO-data pattern (place CSVs + PDFs in `data/customdata/`, run `00_build_solution.py --custom-data`) is functional. The gap is documentation. A new user cannot currently follow any single document to get from raw data to a working agent.

**`data/customdata/README.md` rewrite — required sections:**

1. **What this folder is for** — one-paragraph explanation of the BYO path and when to use it vs. a pre-built scenario pack

2. **Folder structure** — what to place in `tables/` (CSVs) and `documents/` (PDFs):
   - CSVs: UTF-8 encoded, header row required, minimum 2 columns
   - PDFs: any PDF readable by Azure AI Search

3. **Quick start** — exact two-command sequence:
   ```bash
   azd up
   python scripts/00_build_solution.py \
     --custom-data data/customdata \
     --industry "<your industry>" \
     --usecase "<your use case>"
   ```

4. **Azure-only mode** — prerequisites, command, expected output

5. **Fabric mode** — additional prerequisites (`FABRIC_WORKSPACE_ID`), command, expected output, any manual post-creation steps

6. **How `ontology_config.json` is generated** — brief explanation of `generate_config_from_csv.py`; how to inspect and edit the generated file before running the full pipeline

7. **Troubleshooting** — table of common errors and fixes:

   | Error | Cause | Fix |
   |-------|-------|-----|
   | `No CSV files found in tables/` | Empty `tables/` folder | Place at least one `.csv` file in `data/customdata/tables/` |
   | `--industry` is required | Missing argument | Add `--industry "<your industry>"` to the command |
   | `FABRIC_WORKSPACE_ID not found` | Env var not set for Fabric mode | Set `FABRIC_WORKSPACE_ID` in `.env` |
   | CSV encoding error | Non-UTF-8 file | Re-save the CSV as UTF-8 |

**Input validation changes** (in `scripts/00_build_solution.py` and `scripts/generate_config_from_csv.py`):
1. Before step 01: assert `<custom-data>/tables/` contains at least one `.csv` — error and exit if not
2. Warn (do not block) if `<custom-data>/documents/` is empty
3. If `FABRIC_WORKSPACE_ID` is set, print a warning that the Fabric step will be skipped for custom data and provide the manual remediation command

**Sample data** (add to `data/customdata/`):
- `tables/patients.csv` — columns: `patient_id`, `name`, `age`, `diagnosis`, `admission_date`, `discharge_date`; ~50 fictional rows
- `tables/appointments.csv` — columns: `appointment_id`, `patient_id`, `doctor`, `date`, `type`, `status`; ~50 fictional rows; `patient_id` values match `patients.csv`
- `documents/hospital_policy.pdf` — 1–2 page fictional document covering appointment scheduling and discharge policy

All sample data must be clearly fictional (no real names, no real medical information).

**Done when:** A user with no prior knowledge can follow `data/customdata/README.md` alone and get a working agent from their own data in both Azure-only and Fabric modes.

---

## 4. Deploy with AVM

### Add an AVM-based deployment path

**What it is:** The current `infra/deploy_*.bicep` modules are hand-authored. An AVM-based path replaces them with Azure Verified Modules that are tested, maintained, and meet Azure's baseline quality bar.

**Scope:** Identify and integrate AVM modules for all provisioned resource types:

| Resource type | AVM module (candidate) |
|--------------|------------------------|
| AI Foundry (AI Hub + Project) | `avm/res/machine-learning-services/workspace` |
| App Service Plan + Web App | `avm/res/web/serverfarm`, `avm/res/web/site` |
| Azure Cosmos DB | `avm/res/document-db/database-account` |
| Azure SQL | `avm/res/sql/server` |
| Container Registry | `avm/res/container-registry/registry` |
| AI Search | `avm/res/search/search-service` |
| Key Vault | `avm/res/key-vault/vault` |
| Managed Identity | `avm/res/managed-identity/user-assigned-identity` |

**File layout:**
```
infra/
└── avm/
    ├── main.bicep          ← AVM entry point (mirrors infra/main.bicep structure)
    ├── main.parameters.json
    └── modules/
        ├── ai_foundry.bicep
        ├── app_service.bicep
        ├── cosmos_db.bicep
        ├── sql.bicep
        ├── container_registry.bicep
        ├── ai_search.bicep
        └── key_vault.bicep
```

### Include security controls

Enforce the following in all AVM modules by default:

- **Private endpoints** — all data-plane services (Cosmos DB, SQL, AI Search, Storage, Key Vault) use private endpoints; no public network access
- **Managed identity** — all App Service and AI Foundry resources use system-assigned or user-assigned managed identities; no connection strings or keys in app settings
- **RBAC least-privilege** — assign only the minimum required built-in roles; no `Owner` or `Contributor` at resource scope
- **Key Vault integration** — all secrets (connection strings, API keys) stored in Key Vault; app settings reference Key Vault secret URIs

### Include compliance considerations

Apply the following to all resources in the AVM deployment:

- **Resource locks** — apply `CanNotDelete` locks to all production resources
- **Diagnostic settings** — send all resource logs and metrics to a Log Analytics workspace
- **Audit logging** — enable audit logs for SQL, Cosmos DB, and Key Vault
- **Tagging policy** — enforce tags: `environment`, `project`, `owner`, `cost-center` on all resources
- **Standardized SKUs** — define minimum production SKUs per resource type; no free-tier SKUs in the AVM path

### Standardized provisioning

- Naming: follow the [Azure naming convention](https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-naming) (`<type>-<project>-<env>-<region>-<instance>`)
- Region constraints: validate that the selected region supports all required resource types before deployment
- Parameter defaults: all AVM modules expose the same parameter names as their non-AVM counterparts so existing `.env` files work without modification

**Documentation (`documents/DeploymentGuide.md`):**
- Add an "AVM deployment" section covering prerequisites, how to select the AVM path, and any parameter differences
- Document the security controls that are active by default and how to opt out if needed
- Include a comparison table: default Bicep path vs. AVM path (security posture, provisioning time, customizability)

**Done when:** `azd up` with `DEPLOY_WITH_AVM=true` (or a separate `azure-avm.yaml` target) provisions all resources using AVM modules with private endpoints, managed identity, RBAC, Key Vault, resource locks, diagnostics, and tags applied automatically.

