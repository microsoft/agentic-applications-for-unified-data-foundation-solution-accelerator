# Generate Custom Data

Generate AI-powered datasets for any industry and use case. This is ideal for POCs, demos, and workshops where you want realistic data without bringing your own.

## How It Works

The pipeline uses Azure OpenAI to:
1. Generate a custom Python script tailored to your industry/use case
2. Execute that script to create realistic CSV tables with proper relationships
3. Generate PDF documents relevant to your domain
4. Create `config/ontology_config.json` with table schemas and relationships
5. Generate sample questions for testing

All generated artifacts are saved to a scenario folder and used by the remaining pipeline steps.

## Quick Start

### Option 1: Use the Default Scenario (Simplest)

Run without any flags — the `default` scenario generates Telecommunications data automatically:

```bash
python infra/scripts/post-provision/00_build_solution.py
```

This generates a small dataset for "Network operations with outage tracking and trouble ticket management".

### Option 2: Register a Custom Generate Scenario

1. **Add an entry to [`data/scenarios/scenarios.json`](../data/scenarios/scenarios.json):**

```json
{
  "my_energy": {
    "folder": "data/scenarios/my_energy",
    "industry": "Energy",
    "usecase": "Grid monitoring and outage response",
    "data_size": "medium",
    "type": "generate",
    "description": "AI-generated energy grid monitoring scenario",
    "landing_text": "Ask about grid outages, response times, and maintenance schedules...",
    "app_title": "Contoso Energy",
    "app_header": "| Grid Operations Agents"
  }
}
```

2. **Run the pipeline:**

```bash
python infra/scripts/post-provision/00_build_solution.py --scenario my_energy
```

The pipeline will:
- Create the scenario folder automatically
- Run step 01 (AI data generation) into that folder
- Continue with steps 02–08 (Fabric, agent, app deployment)

### Option 3: Override Industry/Use Case via CLI

You can override the scenario metadata with CLI flags:

```bash
python infra/scripts/post-provision/00_build_solution.py --scenario my_energy --industry "Renewable Energy" --usecase "Solar farm monitoring" --size large
```

## Scenario JSON Fields for `generate` Type

| Field | Required | Description |
|-------|----------|-------------|
| `folder` | Yes | Output path (relative to project root) — created automatically if missing |
| `industry` | Yes | Domain name passed to the AI generator |
| `usecase` | Yes | Use case description passed to the AI generator |
| `data_size` | Yes | `small`, `medium`, or `large` — controls table row counts and document count |
| `type` | Yes | Must be `"generate"` for synthetic data generation |
| `description` | No | Shown with `--list-scenarios` |
| `landing_text` | No | Welcome message in the chat UI |
| `app_title` | No | Browser tab title |
| `app_header` | No | App header text |

## Data Size Options

| Size | Primary Table Rows | Secondary Table Rows | Tables | Documents |
|------|-------------------|---------------------|--------|-----------|
| `small` | 16 | 40 | 2–3 | 3 |
| `medium` | 50 | 200 | 4–5 | 5 |
| `large` | 200 | 1000 | 6–8 | 8 |

## What Gets Generated

After step 01 completes, your scenario folder will contain:

```
data/scenarios/my_energy/
├── _generated_script.py        ← The AI-written data generation script
├── config/
│   ├── ontology_config.json    ← Table schemas, keys, relationships
│   └── sample_questions.txt    ← Example questions for testing
├── tables/
│   └── *.csv                   ← Generated CSV tables
└── documents/
    └── *.pdf                   ← Generated reference documents
```

## Re-running with Different Parameters

To regenerate data for an existing scenario:

```bash
# Delete existing generated data (keeps the scenarios.json entry)
rm -rf data/scenarios/my_energy/tables data/scenarios/my_energy/documents data/scenarios/my_energy/config

# Re-run with different size
python infra/scripts/post-provision/00_build_solution.py --scenario my_energy --size large
```

## Listing Available Scenarios

```bash
python infra/scripts/post-provision/00_build_solution.py --list-scenarios
```

Output:
```
Available Scenarios (5):
--------------------------------------------------------------------------------
  Name            Type       Industry        Use Case
--------------------------------------------------------------------------------
  insurance       prebuilt   Insurance       Claims processing and customer management
  retail          prebuilt   Retail          Inventory and sales operations
  default         prebuilt   Telecommunications Network operations
  default_large   prebuilt   Telecommunications Network operations and outage tracking
  my_energy       generate   Energy          Grid monitoring and outage response
--------------------------------------------------------------------------------

  Types: prebuilt = ready-to-use data
         custom   = bring your own CSVs (auto-generates config)
         generate = AI creates synthetic data for your industry/usecase
```

## Comparison: Three Scenario Types

| | Prebuilt | Custom (BYOD) | Generate |
|---|---------|---------------|----------|
| **Data source** | Included in repo | User provides CSVs/PDFs | AI generates everything |
| **Step 01** | Skipped | Skipped | Runs |
| **Config generation** | Already exists | Auto-generated from CSVs | AI generates |
| **Best for** | Quick demos | Real enterprise data | POC with custom domain |
| **Guide** | [Deployment Guide](./DeploymentGuide.md) | [Bring Your Own Data](../data/customdata/README.md) | This document |

## Troubleshooting

- **"ERROR: Industry is required"** — Ensure `industry` is set in `scenarios.json` or pass `--industry` on the CLI
- **Step 01 takes too long** — Large datasets require more AI calls; try `small` first
- **Generated schema is incorrect** — Delete `config/ontology_config.json` and regenerate, or edit it manually and re-run from step 03: `--from 03`
- **Need more tables/relationships** — Use `large` size which generates 6–8 tables with 5–7 relationships
