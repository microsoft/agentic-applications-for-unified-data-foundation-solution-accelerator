"""
Shared utilities for building ontology config and generating sample questions.

Used by both:
  - 01_generate_data.py   (AI-generated data flow)
  - generate_config_from_csv.py  (custom / BYO data flow)

Functions:
    build_tables_from_csvs   - Parse CSV files → table definitions + FK relationships
    build_ontology_config    - Assemble ontology_config.json content
    init_ai_client           - Initialize Azure OpenAI via AIProjectClient
    generate_sample_questions - Generate questions via AI (with heuristic fallback)
    write_config_files       - Write ontology_config.json + sample_questions.txt
"""

import json
import os
import sys

import pandas as pd


# ============================================================================
# Pandas dtype → ontology type mapping
# ============================================================================

def pandas_dtype_to_ontology(dtype_str: str) -> str:
    """Map a pandas dtype string to an ontology type."""
    dtype_str = str(dtype_str)
    if dtype_str.startswith("int"):
        return "BigInt"
    if dtype_str.startswith("float"):
        return "Float"
    if dtype_str.startswith("bool"):
        return "Boolean"
    if "datetime" in dtype_str:
        return "DateTime"
    return "String"


def _looks_like_date_column(col_name: str, series: "pd.Series") -> bool:
    """Return True if *series* appears to contain date/datetime values.

    Heuristics:
      1. Column name contains 'date', 'time', '_at', '_on', '_dt'.
      2. A sample of non-null values successfully parses as dates.
    """
    import re
    name_hint = bool(re.search(r"date|_at$|_on$|_dt$|timestamp|_time$", col_name, re.I))

    # Try parsing a sample of non-null values
    sample = series.dropna().head(20)
    if sample.empty:
        return name_hint

    try:
        parsed = pd.to_datetime(sample, errors="coerce", infer_datetime_format=True)
        pct_parsed = parsed.notna().sum() / len(sample)
        # If >80 % parse as dates AND (name hints or 100 % parse), treat as date
        if pct_parsed >= 1.0:
            return True
        if pct_parsed >= 0.8 and name_hint:
            return True
    except Exception:
        pass
    return False


def _has_time_component(series: "pd.Series") -> bool:
    """Return True if the date values include a non-midnight time part (→ DateTime)."""
    sample = series.dropna().head(20)
    try:
        parsed = pd.to_datetime(sample, errors="coerce", infer_datetime_format=True).dropna()
        # If any value has a non-zero time component, it's DateTime
        return any(t.hour != 0 or t.minute != 0 or t.second != 0 for t in parsed)
    except Exception:
        return False


# ============================================================================
# Build table definitions + relationships from CSVs
# ============================================================================

def build_tables_from_csvs(tables_dir: str):
    """Read all CSVs from tables_dir, infer schema, detect PKs and FK relationships.

    Returns:
        tables: dict  {table_name: {columns, types, key, source_table}}
        relationships: list  [{name, from, to, fromKey, toKey}]
    """
    csv_files = sorted([f for f in os.listdir(tables_dir) if f.endswith(".csv")])
    if not csv_files:
        raise ValueError(f"No CSV files found in {tables_dir}")

    tables = {}

    for csv_file in csv_files:
        table_name = os.path.splitext(csv_file)[0]
        csv_path = os.path.join(tables_dir, csv_file)

        df = pd.read_csv(csv_path, nrows=100)  # sample for type inference

        columns = list(df.columns)
        types = {}
        for col in columns:
            base_type = pandas_dtype_to_ontology(df[col].dtype)
            # Heuristic date detection: pandas reads CSV dates as object/string,
            # so we try to parse columns whose name contains "date" or "time".
            if base_type == "String" and _looks_like_date_column(col, df[col]):
                if _has_time_component(df[col]):
                    base_type = "DateTime"
                else:
                    base_type = "Date"
            types[col] = base_type

        # Heuristic PK detection:
        #   1. <table_name>_id  or  <singular>_id  or  id
        #   2. First column ending with _id
        #   3. First column
        key = None
        singular = table_name.rstrip("s")
        for candidate in [f"{table_name}_id", f"{singular}_id", "id"]:
            if candidate in columns:
                key = candidate
                break
        if key is None:
            id_cols = [c for c in columns if c.endswith("_id")]
            key = id_cols[0] if id_cols else columns[0]

        tables[table_name] = {
            "columns": columns,
            "types": types,
            "key": key,
            "source_table": table_name,
        }

    # Detect foreign-key relationships
    relationships = []
    table_keys = {tname: tdef["key"] for tname, tdef in tables.items()}

    for tname, tdef in tables.items():
        for col in tdef["columns"]:
            if col == tdef["key"]:
                continue  # skip own primary key
            for other_name, other_key in table_keys.items():
                if other_name == tname:
                    continue
                if col == other_key:
                    rel_name = f"{tname}_to_{other_name}"
                    if not any(r["name"] == rel_name for r in relationships):
                        relationships.append({
                            "name": rel_name,
                            "from": tname,
                            "to": other_name,
                            "fromKey": col,
                            "toKey": other_key,
                        })

    return tables, relationships


# ============================================================================
# Build ontology config dict
# ============================================================================

def build_ontology_config(tables: dict, relationships: list,
                          industry: str, usecase: str) -> dict:
    """Assemble an ontology_config dict in the format downstream scripts expect."""
    industry_slug = industry.lower().replace(" ", "_")[:30]
    return {
        "scenario": industry_slug,
        "name": usecase,
        "description": usecase,
        "tables": tables,
        "relationships": relationships,
    }


# ============================================================================
# AI client initialization
# ============================================================================

def init_ai_client():
    """Initialize Azure OpenAI client via AIProjectClient.

    Returns:
        (client, model)  on success
        (None, None)     if AZURE_AI_PROJECT_ENDPOINT is not set
    """
    endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
    if not endpoint:
        return None, None

    from azure.identity import DefaultAzureCredential
    from azure.ai.projects import AIProjectClient

    credential = DefaultAzureCredential()
    project_client = AIProjectClient(endpoint=endpoint, credential=credential)
    client = project_client.get_openai_client()
    model = (os.getenv("AZURE_CHAT_MODEL")
             or os.getenv("MODEL_DEPLOYMENT", "gpt-4o-mini"))
    return client, model


# ============================================================================
# Sample-questions generation (AI + heuristic fallback)
# ============================================================================

def generate_sample_questions(tables: dict, relationships: list,
                              doc_files: list, industry: str, usecase: str,
                              tables_dir: str,
                              client=None, model=None) -> str:
    """Generate sample_questions.txt content.

    Uses Azure OpenAI when *client* and *model* are provided;
    falls back to a heuristic generator otherwise.
    """
    if client and model:
        try:
            return _generate_questions_ai(
                tables, relationships, doc_files,
                industry, usecase, tables_dir, client, model,
            )
        except Exception as e:
            print(f"  [WARN] AI question generation failed: {e}")
            print("  Falling back to heuristic question generation...")

    return _generate_questions_fallback(tables, relationships, doc_files)


# -- AI path -----------------------------------------------------------------

def _generate_questions_ai(tables, relationships, doc_files,
                           industry, usecase, tables_dir,
                           client, model) -> str:
    """Call Azure OpenAI to produce domain-aware sample questions."""

    from datetime import datetime

    today_str = datetime.now().strftime("%Y-%m-%d")

    # Build per-table summaries (schema + 5 sample rows + date-range info)
    table_summaries = []
    date_range_notes = []  # collected across all tables

    for tname, tdef in tables.items():
        csv_path = os.path.join(tables_dir, f"{tname}.csv")
        df = pd.read_csv(csv_path, nrows=5)
        sample_rows = df.to_string(index=False)

        # Detect date columns and compute their range from full data
        df_full = pd.read_csv(csv_path)
        date_cols_info = []
        for col in tdef["columns"]:
            if tdef["types"].get(col) in ("Date", "DateTime"):
                date_cols_info.append(col)
            elif "date" in col.lower():
                # Also try to parse columns with 'date' in the name
                date_cols_info.append(col)

        col_range_lines = []
        for col in date_cols_info:
            try:
                parsed = pd.to_datetime(df_full[col], errors="coerce").dropna()
                if not parsed.empty:
                    mn, mx = parsed.min().strftime("%Y-%m-%d"), parsed.max().strftime("%Y-%m-%d")
                    col_range_lines.append(f"    {col}: {mn} to {mx}")
                    date_range_notes.append(f"{tname}.{col}: {mn} to {mx}")
            except Exception:
                pass

        date_range_block = ""
        if col_range_lines:
            date_range_block = "\n  Date column ranges:\n" + "\n".join(col_range_lines)

        table_summaries.append(
            f"Table: {tname}\n"
            f"  Primary Key: {tdef['key']}\n"
            f"  Columns & Types: {json.dumps(tdef['types'], indent=4)}\n"
            f"  Sample rows:\n{sample_rows}"
            f"{date_range_block}"
        )

    # Relationship summary
    if relationships:
        rel_lines = [f"  - {r['from']}.{r['fromKey']} -> {r['to']}.{r['toKey']}"
                     for r in relationships]
        relationship_summary = "Relationships:\n" + "\n".join(rel_lines)
    else:
        relationship_summary = "Relationships: None detected"

    # Document summary
    if doc_files:
        doc_names = [f.replace(".pdf", "").replace("_", " ") for f in doc_files]
        doc_summary = "PDF Documents:\n" + "\n".join(f"  - {name}" for name in doc_names)
    else:
        doc_summary = "PDF Documents: None"

    # Date context for the prompt
    if date_range_notes:
        date_context = (
            f"\n=== DATE CONTEXT ===\n"
            f"Today's date: {today_str}\n"
            f"Date ranges in the data:\n"
            + "\n".join(f"  - {n}" for n in date_range_notes)
        )
    else:
        date_context = f"\nToday's date: {today_str}"

    prompt = f"""You are generating sample questions for a demo agent that can:
1. Query SQL tables (structured data)
2. Search PDF documents (AI Search)
3. Combine both sources for insight

Industry: {industry}
Use Case: {usecase}
{date_context}

=== DATABASE SCHEMA ===
{chr(10).join(table_summaries)}

{relationship_summary}

=== DOCUMENTS ===
{doc_summary}

Generate a sample_questions.txt file with EXACTLY this structure:

=== SQL QUESTIONS (Fabric Data) ===
1. [question]
2. [question]
3. [question]
4. [question]
5. [question]

=== DOCUMENT QUESTIONS (AI Search) ===
1. [question]
2. [question]
3. [question]
4. [question]
5. [question]

=== COMBINED INSIGHT QUESTIONS ===
1. [question]
2. [question]
3. [question]
4. [question]
5. [question]

RULES:
- SQL questions MUST reference actual column names and tables from the schema above.
- Include a mix: counts, aggregations (SUM/AVG), group-by, top-N, joins across tables.
- TIME-AWARE QUESTIONS (IMPORTANT): If the data has date columns, at least 2-3 SQL questions
  MUST use relative time phrases like "in the last month", "this quarter", "in the past 90 days",
  "last week", or "year to date". Use the date ranges shown above to pick time windows that
  will actually return results. For example, if order_date ranges from 2025-09-04 to 2026-03-04,
  asking "how many orders were placed last month" will return results.
  Do NOT use absolute dates in questions — use natural relative phrases.
- Document questions MUST reference topics from the actual PDF document names above.
- Combined questions MUST need BOTH SQL data AND document content to answer.
  For example: "Are we meeting the [policy] requirements based on our [table] data?"
- Do NOT include threshold numbers in combined questions — the agent should discover
  them from documents.
- Make questions sound natural, like a business user would ask them.
- Each question should be specific enough to produce an interesting answer.

Return ONLY the formatted text content (no markdown code fences, no explanations).
"""

    response = client.responses.create(
        model=model,
        instructions=(
            "You are an expert at writing demo questions for AI agents. "
            "Generate questions that showcase the agent's ability to query "
            "data and search documents. "
            "Return ONLY the formatted text, no markdown fences."
        ),
        input=prompt,
    )

    # Extract text from response
    questions_text = ""
    for item in response.output:
        if hasattr(item, "type") and item.type == "message":
            for content in item.content:
                if hasattr(content, "text"):
                    questions_text += content.text

    # Strip markdown fences if present
    if questions_text.startswith("```"):
        lines = questions_text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        questions_text = "\n".join(lines)

    questions_text = questions_text.strip()

    # Validate: must contain all three sections
    if ("SQL QUESTIONS" in questions_text
            and "DOCUMENT QUESTIONS" in questions_text
            and "COMBINED" in questions_text):
        q_count = sum(1 for line in questions_text.split("\n")
                      if line.strip() and line.strip()[0].isdigit() and ". " in line)
        print(f"  [OK] Generated {q_count} questions via AI")
        return questions_text

    raise ValueError("AI response missing expected question sections")


# -- Heuristic fallback -------------------------------------------------------

def _generate_questions_fallback(tables, relationships, doc_files) -> str:
    """Build basic sample questions without AI (used when endpoint is unavailable)."""

    def _h(s):
        return s.replace("_", " ").replace(".pdf", "").strip()

    table_names = list(tables.keys())
    lines = ["=== SQL QUESTIONS (Fabric Data) ==="]
    q = 1

    for tname in table_names[:3]:
        tdef = tables[tname]
        lines.append(f"{q}. How many {_h(tname)} are there in total?")
        q += 1
        num_cols = [c for c in tdef["columns"]
                    if tdef["types"].get(c) in ("Float", "Double", "BigInt")
                    and not c.endswith("_id")]
        if num_cols:
            lines.append(f"{q}. What is the average {_h(num_cols[0])} across all {_h(tname)}?")
            q += 1

    for rel in relationships[:2]:
        lines.append(f"{q}. How many {_h(rel['from'])} are linked to each {_h(rel['to'])}?")
        q += 1

    lines += ["", "=== DOCUMENT QUESTIONS (AI Search) ==="]
    if doc_files:
        for i, doc in enumerate(doc_files[:4], 1):
            lines.append(f"{i}. What does the {_h(doc)} cover?")
        lines.append(f"{min(len(doc_files), 4) + 1}. Summarize the key policies and guidelines.")
    else:
        lines.append("1. (Add PDF documents to documents/ folder)")

    lines += ["", "=== COMBINED INSIGHT QUESTIONS ==="]
    if doc_files and table_names:
        lines.append(
            f"1. Based on the {_h(doc_files[0])}, what rules apply to the {_h(table_names[0])} data?"
        )
        if len(doc_files) > 1:
            lines.append(
                f"2. Are there any issues in the {_h(table_names[0])} data "
                f"according to the {_h(doc_files[1])}?"
            )
    else:
        lines.append("1. (Add questions that combine data and document knowledge)")

    return "\n".join(lines)


# ============================================================================
# File I/O
# ============================================================================

def write_config_files(config_dir: str, ontology_config: dict, questions_text: str):
    """Write ontology_config.json and sample_questions.txt to *config_dir*."""
    os.makedirs(config_dir, exist_ok=True)

    config_path = os.path.join(config_dir, "ontology_config.json")
    with open(config_path, "w") as f:
        json.dump(ontology_config, f, indent=4)
    print(f"  [OK] Wrote {config_path}")

    questions_path = os.path.join(config_dir, "sample_questions.txt")
    with open(questions_path, "w") as f:
        f.write(questions_text + "\n")
    print(f"  [OK] Wrote {questions_path}")
