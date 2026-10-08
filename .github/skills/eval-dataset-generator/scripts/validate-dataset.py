#!/usr/bin/env python3
"""Validate a dataset.jsonl evaluation file for schema and record count.

Works identically on Windows, macOS, and Linux (no shell-specific logic).

Usage:
    python validate-dataset.py --dataset <path> [--expected-count N]

Behavior:
    * Reads --dataset line by line, skipping blank lines.
    * Confirms every non-blank line is valid JSON with exactly the keys
      "query" and "ground_truth", both non-empty strings.
    * Prints the total record count.
    * When --expected-count is provided, exits with a non-zero status and
      an error message if the total does not match.

Run this after authoring or trimming a dataset.jsonl and before removing
the intermediate extracted-text staging directory.
"""
import argparse
import json
import sys
from pathlib import Path

EXPECTED_KEYS = {"query", "ground_truth"}


def validate_dataset(path: Path) -> int:
    """Validate every record in the dataset file. Returns the record count.

    Raises ValueError on the first schema violation encountered.
    """
    count = 0
    with path.open(encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_number}: invalid JSON ({exc})") from exc

            if not isinstance(record, dict) or set(record.keys()) != EXPECTED_KEYS:
                raise ValueError(f"line {line_number}: expected keys {EXPECTED_KEYS}, got {record.keys() if isinstance(record, dict) else type(record)}")

            for key in EXPECTED_KEYS:
                if not isinstance(record[key], str) or not record[key].strip():
                    raise ValueError(f"line {line_number}: '{key}' must be a non-empty string")

            count += 1

    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a dataset.jsonl evaluation file.")
    parser.add_argument("--dataset", required=True, help="Path to the dataset.jsonl file to validate.")
    parser.add_argument("--expected-count", type=int, default=None, help="Expected total record count.")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.is_file():
        print(f"ERROR: Dataset file not found: {dataset_path}", file=sys.stderr)
        return 1

    try:
        count = validate_dataset(dataset_path)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"total records: {count}")

    if args.expected_count is not None and count != args.expected_count:
        print(f"ERROR: expected {args.expected_count} records but found {count}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
