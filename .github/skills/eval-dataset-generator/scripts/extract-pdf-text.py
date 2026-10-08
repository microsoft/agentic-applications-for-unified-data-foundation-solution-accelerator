#!/usr/bin/env python3
"""Extract text content from PDF file(s) using pypdf.

Works identically on Windows, macOS, and Linux (no shell-specific logic),
so this single script serves as the cross-platform extraction step.

Usage:
    python extract-pdf-text.py --input <file-or-dir> --output <file-or-dir> [--recursive]

Behavior:
    * When --input is a single PDF file, --output may be a specific .txt file
      path or a directory (the file is written as <stem>.txt inside it).
    * When --input is a directory, every *.pdf file found is extracted to a
      same-named .txt file inside --output (created automatically). Pass
      --recursive to also search subdirectories.

Each extracted .txt file contains page-marked text, e.g.:
    --- PAGE 1 ---
    <page 1 text>
    --- PAGE 2 ---
    <page 2 text>

These .txt files are intermediate artifacts only. After authoring the
evaluation dataset, remove them with cleanup-extracted-text.ps1/.sh.
"""
import argparse
import sys
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    print("ERROR: pypdf is required. Install with: pip install pypdf", file=sys.stderr)
    sys.exit(1)


def extract_pdf_text(pdf_path: Path) -> tuple[str, int]:
    """Extract text from every page of a PDF, marked with page headers.

    Returns a tuple of (marked_text, page_count).
    """
    reader = PdfReader(str(pdf_path))
    parts = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        parts.append(f"--- PAGE {i} ---\n{text}")
    return "\n".join(parts), len(reader.pages)


def resolve_output_file(pdf_path: Path, output: Path, output_is_dir: bool) -> Path:
    if output_is_dir:
        return output / (pdf_path.stem + ".txt")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract text from PDF file(s).")
    parser.add_argument("--input", required=True, help="Path to a PDF file or a directory containing PDFs.")
    parser.add_argument("--output", required=True, help="Output .txt file path, or output directory when --input is a directory.")
    parser.add_argument("--recursive", action="store_true", help="Recurse into subdirectories when --input is a directory.")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"ERROR: Input path not found: {input_path}", file=sys.stderr)
        return 1

    if input_path.is_dir():
        pattern = "**/*.pdf" if args.recursive else "*.pdf"
        pdf_files = sorted(input_path.glob(pattern))
        if not pdf_files:
            print(f"WARNING: No PDF files found under {input_path}", file=sys.stderr)
            return 0

        output_path.mkdir(parents=True, exist_ok=True)
        for pdf_file in pdf_files:
            text, page_count = extract_pdf_text(pdf_file)
            out_file = resolve_output_file(pdf_file, output_path, output_is_dir=True)
            out_file.write_text(text, encoding="utf-8")
            print(f"Extracted {pdf_file.name} -> {out_file} ({page_count} pages, {len(text)} chars)")
    else:
        output_is_dir = output_path.is_dir() or output_path.suffix == ""
        if output_is_dir:
            output_path.mkdir(parents=True, exist_ok=True)
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)

        out_file = resolve_output_file(input_path, output_path, output_is_dir)
        text, page_count = extract_pdf_text(input_path)
        out_file.write_text(text, encoding="utf-8")
        print(f"Extracted {input_path.name} -> {out_file} ({page_count} pages, {len(text)} chars)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
