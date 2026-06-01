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

### Option 1: Register a Custom Generate Scenario

1. **Add an entry to [`data/scenarios/scenarios.json`](../data/scenarios/scenarios.json):**

```json
{
  "my_energy": {
    "folder": "data/scenarios/my_energy",
    "industry": "Energy",
    "usecase": "Grid monitoring and outage response",
    "data_size": "medium",
    "type": "custom",
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

### Option 2: Generate Directly (Without Pre-registering)

You can run the data generator directly with just industry and use case — no `scenarios.json` entry needed:

```bash
python infra/scripts/post-provision/00_build_solution.py --only 01 --industry "Energy" --usecase "Grid monitoring and outage response" --size medium
```

This will:
- Generate data into `data/scenarios/energy/`
- **Auto-register** the scenario as `"energy"` in `scenarios.json`
- Print: `[OK] Registered scenario 'energy' in scenarios.json`

You can then run the full pipeline with:
```bash
python infra/scripts/post-provision/00_build_solution.py --scenario energy
```

To control the output location explicitly:
```bash
python infra/scripts/post-provision/00_build_solution.py --only 01 --industry "Energy" --usecase "Grid monitoring" --size medium --output-dir data/scenarios/my_energy
```

### Option 3: Override Industry/Use Case via CLI

You can override the scenario metadata with CLI flags on either the orchestrator or step 01 directly:

```bash
# Via orchestrator
python infra/scripts/post-provision/00_build_solution.py --scenario my_energy --industry "Renewable Energy" --usecase "Solar farm monitoring" --size large

# Via step 01 directly
python infra/scripts/post-provision/00_build_solution.py --only 01 --scenario my_energy --industry "Renewable Energy" --size large
```

## Scenario JSON Fields for `custom` Type

| Field | Required | Description |
|-------|----------|-------------|
| `folder` | Yes | Output path (relative to project root) — created automatically if missing |
| `industry` | Yes | Domain name passed to the AI generator |
| `usecase` | Yes | Use case description passed to the AI generator |
| `data_size` | Yes | `small`, `medium`, or `large` — controls table row counts and document count |
| `type` | Yes | Must be `"custom"` for data generation |
| `description` | No | Shown with `--list-scenarios` |
| `landing_text` | No | Welcome message in the chat UI |
| `app_title` | No | Browser tab title |
| `app_header` | No | App header text |

> **Note:** When using Option 2 (direct generation without pre-registering), these fields are auto-populated in `scenarios.json` from your CLI args.

## Step 01 CLI Reference

```
python infra/scripts/post-provision/00_build_solution.py --only 01 [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `--scenario NAME` | Load config from `scenarios.json` (folder, industry, usecase, size) |
| `--industry TEXT` | Industry name (overrides scenario/env) |
| `--usecase TEXT` | Use case description (overrides scenario/env) |
| `--size small\|medium\|large` | Data size (overrides scenario/env) |
| `--output-dir PATH` | Output directory (overrides scenario folder/env) |

**Resolution priority** (for each parameter):
1. CLI flag (`--industry`, `--output-dir`, etc.)
2. Scenario config (if `--scenario` provided)
3. `DATA_FOLDER` / `INDUSTRY` / `USECASE` / `DATA_SIZE` env vars
4. Interactive prompt (industry/usecase only)

**Output directory priority:**
1. `--output-dir`
2. Scenario's `folder` field
3. `DATA_FOLDER` env var
4. `data/scenarios/<industry_slug>/` (auto-derived)

**Auto-registration:** After generation, the scenario is automatically registered in `scenarios.json` if not already present.

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

## Troubleshooting

- **"ERROR: Industry is required"** — Ensure `industry` is set in `scenarios.json` or pass `--industry` on the CLI
- **Step 01 takes too long** — Large datasets require more AI calls; try `small` first
- **Generated schema is incorrect** — Delete `config/ontology_config.json` and regenerate, or edit it manually and re-run from step 03: `--from 03`
- **Need more tables/relationships** — Use `large` size which generates 6–8 tables with 5–7 relationships
