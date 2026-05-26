"""
Generate ontology_config.json and sample_questions.txt from CSV files.

Thin CLI wrapper around data_config_utils — the same shared module that
01_generate_data.py uses, so both flows produce config and questions
through identical code.

Usage:
    python generate_config_from_csv.py --data-folder data/customdata \\
        --industry Healthcare --usecase "Patient records and clinical notes"

Output (in <data-folder>/config/):
    ontology_config.json   - table schema, types, keys, relationships
    sample_questions.txt   - AI-generated questions (SQL, document, combined)
"""

import argparse
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))

# Load environment from azd + project .env
from load_env import load_all_env
load_all_env()

from data_config_utils import (
    build_tables_from_csvs,
    build_ontology_config,
    init_ai_client,
    generate_sample_questions,
    write_config_files,
)

# ============================================================================
# CLI
# ============================================================================

parser = argparse.ArgumentParser(
    description="Generate ontology config and sample questions from CSV files"
)
parser.add_argument("--data-folder", required=True,
                    help="Path to custom data folder (must contain tables/)")
parser.add_argument("--industry", required=True,
                    help="Industry name for the scenario")
parser.add_argument("--usecase", required=True,
                    help="Use case description")
args = parser.parse_args()

data_dir = os.path.abspath(args.data_folder)
tables_dir = os.path.join(data_dir, "tables")
config_dir = os.path.join(data_dir, "config")

if not os.path.isdir(tables_dir):
    print(f"ERROR: tables/ folder not found in {data_dir}")
    sys.exit(1)

# ============================================================================
# Build config from CSVs (deterministic — same code as 01 post-step)
# ============================================================================

print(f"  Scanning CSV files in {tables_dir} ...")

tables, relationships = build_tables_from_csvs(tables_dir)
print(f"  Found {len(tables)} table(s): {', '.join(tables.keys())}")
if relationships:
    print(f"  Detected {len(relationships)} relationship(s)")
else:
    print("  No foreign-key relationships detected "
          "(you can add them manually in config/ontology_config.json)")

ontology_config = build_ontology_config(
    tables, relationships, args.industry, args.usecase
)

# ============================================================================
# Generate sample questions (AI-powered, same code as 01 post-step)
# ============================================================================

docs_dir = os.path.join(data_dir, "documents")
doc_files = (sorted([f for f in os.listdir(docs_dir) if f.endswith(".pdf")])
             if os.path.isdir(docs_dir) else [])

client, model = init_ai_client()
if client:
    print("\n  Generating sample questions using AI...")
else:
    print("\n  AZURE_AI_PROJECT_ENDPOINT not set — using heuristic fallback for questions")

questions_text = generate_sample_questions(
    tables, relationships, doc_files,
    args.industry, args.usecase, tables_dir,
    client=client, model=model,
)

# ============================================================================
# Write files
# ============================================================================

write_config_files(config_dir, ontology_config, questions_text)

print(f"\n  Config generated for {len(tables)} table(s) with {len(relationships)} relationship(s).")
config_path = os.path.join(config_dir, "ontology_config.json")
print(f"  You can review and edit: {config_path}")
