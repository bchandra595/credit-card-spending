"""Standard CSV format shared by PDF extraction and the spending analyzer."""

from __future__ import annotations

import io

import pandas as pd

STANDARD_COLUMNS = [
    "Transaction Date",
    "Description",
    "Category",
    "Amount",
    "Source File",
]


def normalized_to_standard(df: pd.DataFrame) -> pd.DataFrame:
    """Convert internal transaction rows to the standard export CSV schema."""
    if df.empty:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    category = df["category"].fillna("").astype(str) if "category" in df.columns else ""

    export = pd.DataFrame(
        {
            "Transaction Date": pd.to_datetime(df["date"]).dt.strftime("%m/%d/%Y"),
            "Description": df["description"],
            "Category": category,
            "Amount": df["amount"].map(lambda v: f"{v:.2f}"),
            "Source File": df["source_file"],
        }
    )
    return export[STANDARD_COLUMNS]


def standard_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialize a standard-format dataframe to CSV bytes."""
    return normalized_to_standard(df).to_csv(index=False).encode("utf-8")


def read_standard_csv(content: bytes) -> pd.DataFrame:
    """Load a standard-format CSV back into normalized transaction rows."""
    table = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)
    missing = [col for col in STANDARD_COLUMNS if col not in table.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")

    from parser import _parse_amount, _parse_date

    rows = []
    for _, row in table.iterrows():
        date = _parse_date(row["Transaction Date"])
        amount = _parse_amount(row["Amount"])
        description = str(row["Description"]).strip()
        if date is None or amount is None or not description:
            continue
        rows.append(
            {
                "date": date,
                "description": description,
                "amount": amount,
                "category": str(row.get("Category", "")).strip(),
                "source_file": str(row.get("Source File", "imported.csv")).strip(),
            }
        )
    if not rows:
        raise ValueError("No valid transactions found in CSV.")
    return pd.DataFrame(rows)
