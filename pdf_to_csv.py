"""Convert credit card statement PDFs to standard CSV."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from csv_format import STANDARD_COLUMNS, standard_to_csv_bytes
from filters import apply_transaction_filters
from pdf_parser import parse_statement_pdf


def extract_pdfs(pdf_files: list) -> pd.DataFrame:
    """Extract and combine transactions from one or more PDF uploads or paths."""
    frames = []
    for item in pdf_files:
        if isinstance(item, (str, Path)):
            path = Path(item)
            content = path.read_bytes()
            name = path.name
        else:
            content = item.getvalue()
            name = item.name
        frames.append(parse_statement_pdf(content, name))

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values("date", ascending=False).reset_index(drop=True)
    return apply_transaction_filters(combined)


def pdfs_to_csv_bytes(pdf_files: list) -> bytes:
    """Extract PDFs and return a combined standard CSV."""
    transactions = extract_pdfs(pdf_files)
    return standard_to_csv_bytes(transactions)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract credit card transactions from PDF statements to CSV.")
    parser.add_argument("pdfs", nargs="+", help="One or more statement PDF files")
    parser.add_argument("-o", "--output", required=True, help="Output CSV path")
    args = parser.parse_args(argv)

    try:
        transactions = extract_pdfs(args.pdfs)
        output = Path(args.output)
        output.write_bytes(standard_to_csv_bytes(transactions))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {len(transactions)} transactions to {output}")
    print(f"Columns: {', '.join(STANDARD_COLUMNS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
