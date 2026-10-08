#!/usr/bin/env bash
# Removes intermediate .txt files generated during PDF text extraction.
#
# Cleans up the staging directory used by extract-pdf-text.py once the
# evaluation dataset.jsonl has been authored and validated, so no generated
# text artifacts are left behind in the repository.
#
# Usage:
#   scripts/cleanup-extracted-text.sh --path <dir> [--keep-directory]
#
# Examples:
#   scripts/cleanup-extracted-text.sh --path .copilot-tracking/pdf-extraction
#   scripts/cleanup-extracted-text.sh --path .copilot-tracking/pdf-extraction --keep-directory

set -euo pipefail

TARGET_PATH=""
KEEP_DIRECTORY=false

usage() {
  echo "Usage: $0 --path <dir> [--keep-directory]" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --path) TARGET_PATH="$2"; shift 2 ;;
    --keep-directory) KEEP_DIRECTORY=true; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown argument: $1" >&2; usage ;;
  esac
done

if [[ -z "$TARGET_PATH" ]]; then
  usage
fi

if [[ ! -e "$TARGET_PATH" ]]; then
  echo "Nothing to clean up. Path does not exist: $TARGET_PATH"
  exit 0
fi

if [[ "$KEEP_DIRECTORY" == true ]]; then
  find "$TARGET_PATH" -type f -iname "*.txt" -delete
  echo "Removed .txt files from $TARGET_PATH (directory retained)."
else
  rm -rf "$TARGET_PATH"
  echo "Removed directory: $TARGET_PATH"
fi
