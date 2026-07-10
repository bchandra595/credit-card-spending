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
2. **Finance Tracker** — upload CSV files and view charts

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

Finance Tracker accepts this format plus native bank CSV exports.

## Project layout

| File | Purpose |
|------|---------|
| `app.py` | Streamlit navigation entry |
| `pages/pdf_to_csv.py` | PDF upload UI |
| `pages/finance_tracker.py` | Spending charts and filters |
| `pdf_to_csv.py` | PDF extraction + CLI |
| `pdf_parser.py` | PDF parsing logic |
| `amex_parser.py` | Amex-specific PDF layout |
| `parser.py` | CSV import |
| `csv_format.py` | Shared CSV schema |
| `filters.py` | Cleaning, autopay removal, refund pairing |
| `merchants.py` | Merchant resolution and categories |
| `merchant_cleaner.py` | Brand/name normalization |
| `merchant_lookup.py` | Optional online categorization |
| `merchant_rules.py` | User overrides (`.cache/merchant_rules.json`) |
| `categories.py` | Keyword and bank-label categories |
