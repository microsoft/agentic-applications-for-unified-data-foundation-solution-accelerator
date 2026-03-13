# Bring Your Own Data

Place your own data files in this folder to run the workshop with custom data
instead of the AI-generated sample data.

## What You Need

Just two folders with your files:

```
data/customdata/
├── tables/
│   └── *.csv                   One CSV file per table
└── documents/
    └── *.pdf                   PDF documents for AI Search
```

The `config/` folder (with `ontology_config.json`) is **auto-generated** from
your CSV files when you run the build script. You'll be prompted for your
industry and use case.

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

**Option A (Fabric + Foundry):**
```bash
python scripts/00_build_solution.py --custom-data data/customdata --fabric-workspace-id <your-workspace-id>
```

**Option B (Azure-only):**
```bash
python scripts/00_build_solution.py --custom-data data/customdata --from 04
```

You will be prompted for:
- **Industry** — e.g. Healthcare, Retail, Manufacturing
- **Use Case** — e.g. Patient records and clinical notes

The script will:
1. Read your CSV files and infer column types, primary keys, and relationships
2. Generate `config/ontology_config.json` automatically
3. Skip step 01 (AI data generation) and run the remaining pipeline steps

## Auto-Generated Config

The generated `config/ontology_config.json` can be reviewed and edited before
re-running the pipeline. It describes:

- Table names, columns, and data types
- Primary key for each table
- Foreign-key relationships between tables

**Supported column types:** `String`, `BigInt`, `Int`, `Float`, `Double`,
`Boolean`, `DateTime`, `Date`, `Time`

## Tips

- Look at `data/default/` for a working example of the expected structure
- If auto-detected keys or relationships are wrong, edit `config/ontology_config.json`
  and re-run from step 04: `python scripts/00_build_solution.py --from 04`
- Delete `config/ontology_config.json` to force regeneration on the next run
- Keep table and column names lowercase with underscores for best SQL compatibility
