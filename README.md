# Credit Card Spending Analyzer

Two-step workflow: convert PDF statements to CSV, then analyze spending.

## Setup

```bash
cd credit-card-spending
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Use the sidebar to switch between:

1. **PDF to CSV** — upload PDF statements, preview extraction, download CSV
2. **Spending Analyzer** (home) — upload CSV files and view charts

## CLI: PDF to CSV

```bash
python pdf_to_csv.py statement.pdf -o transactions.csv
python pdf_to_csv.py jan.pdf feb.pdf -o combined.csv
```

## Standard CSV format

Files produced by **PDF to CSV** use these columns:

| Column | Description |
|--------|-------------|
| Transaction Date | MM/DD/YYYY |
| Description | Merchant / payee |
| Category | Bank category if available |
| Amount | Positive for charges, negative for payments |
| Source File | Original PDF filename |

The spending analyzer accepts this format plus native bank CSV exports.

## Project layout

| File | Purpose |
|------|---------|
| `pages/1_PDF_to_CSV.py` | PDF upload UI |
| `app.py` | Spending charts (CSV only) |
| `pdf_to_csv.py` | PDF extraction + CLI |
| `pdf_parser.py` | PDF parsing logic |
| `parser.py` | CSV import for spending app |
| `csv_format.py` | Shared CSV schema |
