#!/usr/bin/env bash
# Recursively lists files under a directory, optionally filtered by extension.
#
# Discovers source documents (PDFs by default) so they can be handed off to the
# extraction step. Outputs one absolute path per line (or a JSON array).
#
# Usage:
#   scripts/list-documents.sh --path <dir> [--extension pdf] [--format text|json]
#
# Examples:
#   scripts/list-documents.sh --path src/foundry/data/documents
#   scripts/list-documents.sh --path src/foundry/data/documents --format json

set -euo pipefail

TARGET_PATH=""
EXTENSION="pdf"
FORMAT="text"

usage() {
  echo "Usage: $0 --path <dir> [--extension pdf] [--format text|json]" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --path) TARGET_PATH="$2"; shift 2 ;;
    --extension) EXTENSION="$2"; shift 2 ;;
    --format) FORMAT="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown argument: $1" >&2; usage ;;
  esac
done

if [[ -z "$TARGET_PATH" ]]; then
  usage
fi

if [[ ! -d "$TARGET_PATH" ]]; then
  echo "Path not found or not a directory: $TARGET_PATH" >&2
  exit 1
fi

mapfile -t files < <(find "$TARGET_PATH" -type f -iname "*.${EXTENSION}" | sort)

if [[ ${#files[@]} -eq 0 ]]; then
  echo "No files matching '*.${EXTENSION}' found under $TARGET_PATH" >&2
  exit 0
fi

if [[ "$FORMAT" == "json" ]]; then
  printf '['
  for i in "${!files[@]}"; do
    [[ $i -gt 0 ]] && printf ','
    printf '"%s"' "${files[$i]//\"/\\\"}"
  done
  printf ']\n'
else
  printf '%s\n' "${files[@]}"
fi
