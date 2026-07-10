"""Parse credit card statement CSV exports from common bank formats."""

from __future__ import annotations

import io
import re
from datetime import datetime

import pandas as pd

DATE_COLUMNS = ("transaction date", "post date", "date", "trans date", "posted date")
DESC_COLUMNS = ("description", "merchant", "payee", "name", "details", "memo")
AMOUNT_COLUMNS = ("amount", "debit", "charge", "transaction amount", "amount (usd)")
CATEGORY_COLUMNS = ("category", "type", "transaction type")


def _normalize_header(name: str) -> str:
    return re.sub(r"\s+", " ", str(name).strip().lower())


def _pick_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    normalized = {_normalize_header(c): c for c in columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


def _parse_date(value) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%d/%m/%Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _parse_amount(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")") or text.startswith("-")
    text = text.replace("$", "").replace(",", "").replace("(", "").replace(")", "").lstrip("-")
    try:
        amount = float(text)
    except ValueError:
        return None
    return -abs(amount) if negative else amount


def _detect_header_row(raw: pd.DataFrame) -> int:
    for idx in range(min(8, len(raw))):
        row = [_normalize_header(v) for v in raw.iloc[idx].tolist()]
        has_date = any(c in row for c in DATE_COLUMNS)
        has_amount = any(c in row for c in AMOUNT_COLUMNS)
        has_desc = any(c in row for c in DESC_COLUMNS)
        if has_date and has_amount and has_desc:
            return idx
    return 0


def transactions_from_dataframe(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """Map a tabular dataframe with detected columns to normalized transactions."""
    date_col = _pick_column(list(df.columns), DATE_COLUMNS)
    desc_col = _pick_column(list(df.columns), DESC_COLUMNS)
    amount_col = _pick_column(list(df.columns), AMOUNT_COLUMNS)
    category_col = _pick_column(list(df.columns), CATEGORY_COLUMNS)

    if not date_col or not desc_col or not amount_col:
        raise ValueError(
            f"Could not detect required columns in '{source_name}'. "
            f"Found columns: {', '.join(df.columns)}"
        )

    rows = []
    for _, row in df.iterrows():
        date = _parse_date(row.get(date_col))
        description = str(row.get(desc_col, "")).strip()
        amount = _parse_amount(row.get(amount_col))
        if date is None or not description or amount is None or amount == 0:
            continue
        category = ""
        if category_col:
            category = str(row.get(category_col, "")).strip()
        rows.append(
            {
                "date": date,
                "description": description,
                "amount": amount,
                "category": category,
                "source_file": source_name,
            }
        )

    if not rows:
        raise ValueError(f"No valid transactions found in '{source_name}'.")

    return pd.DataFrame(rows)


def parse_statement_csv(content: bytes, source_name: str) -> pd.DataFrame:
    """Return normalized transactions: date, description, amount, category, source_file."""
    raw = pd.read_csv(io.BytesIO(content), header=None, dtype=str, keep_default_na=False)
    header_row = _detect_header_row(raw)
    df = pd.read_csv(io.BytesIO(content), header=header_row, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip() for c in df.columns]
    return transactions_from_dataframe(df, source_name)


def parse_uploaded_file(uploaded) -> pd.DataFrame:
    """Parse a single uploaded CSV statement."""
    from csv_format import read_standard_csv

    content = uploaded.getvalue()
    name = uploaded.name.lower()
    if not name.endswith(".csv"):
        raise ValueError(
            f"'{uploaded.name}' is not a CSV file. "
            "Convert PDF statements first using **PDF to CSV** in the sidebar."
        )

    try:
        return read_standard_csv(content)
    except ValueError:
        return parse_statement_csv(content, uploaded.name)


def parse_uploaded_files(files: list) -> pd.DataFrame:
    """Parse and combine multiple uploaded CSV files."""
    frames = [parse_uploaded_file(uploaded) for uploaded in files]
    combined = pd.concat(frames, ignore_index=True)
    return combined.sort_values("date", ascending=False).reset_index(drop=True)
