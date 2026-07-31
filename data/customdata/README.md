# Bring Your Own Data

Place your own data files in this folder to run the solution with custom data.

## What You Need

Just two folders with your files:

```
data/customdata/
├── tables/
│   └── *.csv                   One CSV file per table
└── documents/
    └── *.pdf                   PDF documents for AI Search
```

> Before running the scripts, replace the files in `data/customdata/tables/` and
`data/customdata/documents/` with your own data files.

The `config/` folder (with `ontology_config.json`) is generated from your CSV
files the first time you run the build script. If industry and use case are not
provided with `--industry` and `--usecase`, you'll be prompted for them.

## CSV files in `tables/`

- One `.csv` file per table (e.g. `orders.csv`, `order_items.csv`)
- First row must be a header row with column names
- The CSV filename (without `.csv`) becomes the table name
- Use lowercase column names with underscores for best SQL compatibility
- Name primary key columns as `<table_name>_id` or `id` for auto-detection
- Name foreign key columns to match the referenced table's key (e.g. `order_id`
  in `order_items.csv` links to `orders.order_id`)

## PDF files in `documents/`

- Place your reference documents (policies, procedures, manuals, etc.) as PDF files
- These are uploaded to Azure AI Search for document-based Q&A
- The agent can answer questions by searching across these documents

## How to Run

After placing your data, run the build pipeline with `--custom-data`:

To reuse an existing Fabric workspace, set the ID first:
```bash
azd env set FABRIC_WORKSPACE_ID <your-workspace-id>
```

Then run the build:
```bash
python infra/scripts/post-provision/00_build_solution.py --custom-data data/customdata
```

> If `FABRIC_WORKSPACE_ID` is not set, a new workspace will be created automatically.

You will be prompted for:
- **Industry** — e.g. Healthcare, Retail, Manufacturing
- **Use Case** — e.g. Patient records and clinical notes

The script will:
1. Read your CSV files and infer column types, primary keys, and relationships
2. Generate `config/ontology_config.json` automatically

## Auto-Generated Config

The generated `config/ontology_config.json` can be reviewed and edited before
re-running the pipeline. It describes:

- Table names, columns, and data types
- Primary key for each table
- Foreign-key relationships between tables

**Supported column types:** `String`, `BigInt`, `Int`, `Float`, `Double`,
`Boolean`, `DateTime`, `Date`, `Time`

## Tips

- Look at `data/scenarios/default/` for a working example of the expected structure
- If auto-detected keys or relationships are wrong, edit `config/ontology_config.json`
  and re-run from step 03: `python infra/scripts/post-provision/00_build_solution.py --from 03`
- Delete `config/ontology_config.json` to force regeneration on the next run
- Keep table and column names lowercase with underscores for best SQL compatibility

## Registering a Custom Scenario

To make your custom data folder available as a named `--scenario`, add an entry to
[`data/scenarios/scenarios.json`](../scenarios/scenarios.json):

```json
{
  "my_scenario": {
    "folder": "data/customdata",
    "industry": "Telecommunications",
    "usecase": "Customer accounts, service plans, network incidents, and support tickets",
    "type": "byod",
    "description": "Custom telecommunications scenario",
    "landing_text": "Ask about subscribers, service plans, outages, and support cases...",
    "app_title": "Telecommunications Agent",
    "app_header": "Telecommunications Data Assistant"
  }
}
```

> **Note:** Set `"type": "byod"` so the pipeline knows to auto-generate `ontology_config.json` from your CSVs.

**Field reference:**

| Field | Required | Description |
|-------|----------|-------------|
| `folder` | Yes | Path to your data folder (relative to project root) containing `tables/` and `documents/` |
| `industry` | Yes | Domain name (e.g. Telecommunications, Retail, Manufacturing). Used for agent prompt context |
| `usecase` | Yes | Brief description of what the data represents. Used for agent prompt context |
| `type` | Yes | `prebuilt` (ready-to-use data) or `byod` (bring your own CSVs, auto-generates config) |
| `description` | No | Human-readable summary shown with `--list-scenarios` |
| `landing_text` | No | Welcome message shown in the chat UI |
| `app_title` | No | Browser tab / app title |
| `app_header` | No | Header text displayed in the app UI |

Then run:
```bash
python infra/scripts/post-provision/00_build_solution.py --scenario my_scenario
```