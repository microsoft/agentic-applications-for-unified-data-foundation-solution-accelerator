---
name: eval-dataset-generator
description: 'Generates an evaluation dataset (JSONL of query/ground_truth pairs) for grounding agent evals from a directory of PDF source documents. Recursively discovers PDFs, extracts their text, authors evaluation Q&A pairs covering every document, and cleans up intermediate files. Use when asked to build eval datasets, ground-truth question/answer pairs, grounding data, or RAG evaluation data from PDF documentation.'
user-invocable: true
compatibility: 'Requires Python 3 with pypdf installed; Bash for helper scripts'
---

# FDE Eval Dataset Generator

## Overview

Builds a `dataset.jsonl` evaluation dataset for grounding an agent, sourced from a
directory of PDF documents. Each record is a JSON object with exactly two keys:

```json
{"query": "<evaluation question>", "ground_truth": "<expected correct answer>"}
```

* `query` is a question a user might ask an agent that is grounded on the PDFs.
* `ground_truth` is the expected correct answer, supported directly by the
  text of one of the source PDFs (never invented or inferred beyond the text).

The workflow has four stages: discover source PDFs, extract their text,
author the Q&A dataset, and clean up intermediate files.

## Prerequisites

* Bash
* Python 3 with `pypdf` installed — verify with: `python -c "import pypdf"`

## Quick Start

1. Ask the user for the path to the directory containing their source PDF
   documents (`<documents-path>` below) if it was not already given. Do not
   assume a default location.

2. Discover the source PDFs recursively:

   ```bash
   scripts/list-documents.sh --path <documents-path>
   ```

3. Extract text from every PDF found into a staging directory:

   ```bash
   python scripts/extract-pdf-text.py --input <documents-path> --output .copilot-tracking/pdf-extraction
   ```

4. Read each generated `.txt` file, then author the `dataset.jsonl` (see
   Dataset Authoring Guidance below). Save it alongside the source documents
   (e.g. `<documents-path>/../dataset.jsonl`) unless the user specifies a
   different output location.

5. Validate the JSONL file (see Validation), then remove the staging directory:

   ```bash
   python scripts/validate-dataset.py --dataset <dataset-path>/dataset.jsonl --expected-count 100
   ```

   ```bash
   scripts/cleanup-extracted-text.sh --path .copilot-tracking/pdf-extraction
   ```

## Dataset Authoring Guidance

An agent authors the actual `query`/`ground_truth` records by reading the
extracted text — there is no script that generates questions automatically.
Follow these rules when writing records:

* **Every source PDF must be represented.** Determine the total record count
  (ask the user if unspecified; default to 100 when not stated) and divide it
  across all documents as evenly as possible. With `N` documents and `T`
  total records, give each document `floor(T/N)` records and distribute the
  `T mod N` remainder one extra each to the largest/densest documents so the
  total is exact.
* **Ground every answer in the extracted text.** Do not fabricate facts,
  numbers, or policies not present in the source. Prefer specific, factual
  questions (thresholds, timeframes, percentages, roles, required
  documentation) that map to a single sentence or clause in the source.
* **Vary phrasing** across questions from the same document/section so the
  dataset tests retrieval robustness, but avoid producing near-duplicate
  question/answer pairs (same fact, same wording) — this inflates count
  without adding evaluation value.
* **Keep `ground_truth` concise** — a direct, self-contained answer (one
  or two sentences), not a restatement of the entire source paragraph.
* **Avoid encoding artifacts.** PDF extraction can mangle special characters
  (e.g., `±` becomes `?`); rewrite these in plain language (e.g., "within
  2 degrees Celsius, plus or minus") rather than copying the raw artifact.

## Validation

Before cleaning up intermediate files, validate the JSONL is well-formed and
matches the expected record count and schema:

```bash
python scripts/validate-dataset.py --dataset <dataset-path>/dataset.jsonl --expected-count 100
```

The script confirms every non-blank line is valid JSON with exactly the
`query`/`ground_truth` keys (both non-empty strings), prints the total
record count, and exits non-zero if `--expected-count` does not match.
Omit `--expected-count` to only print the count. Also manually confirm that
every source PDF contributed at least one record — the script does not know
which document each record came from.

Run the same script after any later edit to `dataset.jsonl` (e.g. trimming
or expanding the record count) to reconfirm the schema and total before
saving the file as final.

## Script Reference

### scripts/list-documents.sh

Recursively lists files under a directory, filtered by extension (default `pdf`).

| Parameter    | Flag (bash)   | Default | Description                                  |
|--------------|---------------|---------|-----------------------------------------------|
| Root path    | `--path`      | (none)  | Directory to scan recursively (required)      |
| Extension    | `--extension` | `pdf`   | File extension to filter on, without the dot  |
| Output format| `--format`    | `text`  | `text` (one path per line) or `json` (array)  |

### scripts/extract-pdf-text.py

Extracts page-marked text from a PDF file or every PDF in a directory using
`pypdf`. Cross-platform (Python); no separate bash/PowerShell version needed.

| Argument      | Description                                                                 |
|---------------|------------------------------------------------------------------------------|
| `--input`     | Path to a single PDF file, or a directory containing PDFs (required)         |
| `--output`    | Output `.txt` file path, or output directory when `--input` is a directory (required) |
| `--recursive` | When `--input` is a directory, also search subdirectories                    |

Output format per file:

```text
--- PAGE 1 ---
<page 1 text>
--- PAGE 2 ---
<page 2 text>
```

### scripts/cleanup-extracted-text.sh

Removes the intermediate `.txt` files produced by `extract-pdf-text.py` once
the dataset has been authored and validated.

| Parameter       | Flag (bash)         | Default | Description                                          |
|-----------------|----------------------|---------|--------------------------------------------------------|
| Staging path    | `--path`             | (none)  | Directory containing generated `.txt` files (required) |
| Keep directory  | `--keep-directory`   | false   | Delete only `*.txt` files, keep the directory itself   |

### scripts/validate-dataset.py

Validates a `dataset.jsonl` file's schema and reports its total record
count. Cross-platform (Python); no separate bash/PowerShell version needed.
Run it after authoring the dataset and after any later edit that changes
the record count (e.g. trimming records down while keeping every source
document represented).

| Argument           | Description                                                          |
|--------------------|------------------------------------------------------------------------|
| `--dataset`        | Path to the `dataset.jsonl` file to validate (required)               |
| `--expected-count` | Expected total record count; exits non-zero on mismatch (optional)    |

## Troubleshooting

* **`ModuleNotFoundError: pypdf`** — run `pip install pypdf` before running `extract-pdf-text.py`.
* **`extract_text()` returns empty string** — the PDF page has no extractable text layer (e.g., a scanned image). That page is skipped; note the gap and, if it is a source document, flag it rather than fabricating content for it.
* **`validate-dataset.py` reports a line error** — a `query`/`ground_truth` record has extra/missing keys, an empty value, or the line is not valid JSON (often from unescaped quotes). Re-check the offending line and re-serialize it as JSON rather than hand-editing raw text.
* **Record count is off after removing duplicates** — recompute the per-document distribution (`floor(T/N)` plus remainder) and add or remove records from the documents with the largest gap first, keeping every document represented.
