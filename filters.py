"""Clean and filter transactions before analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

EMBEDDED_DATE_PREFIX = re.compile(
    r"^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}\s+",
    re.IGNORECASE,
)

AUTOPAY_PATTERNS = (
    "autopay payment received - thank you",
    "autopay payment",
)

@dataclass
class FilterAudit:
    raw_count: int = 0
    autopay_removed: pd.DataFrame = field(default_factory=pd.DataFrame)
    duplicates_removed: pd.DataFrame = field(default_factory=pd.DataFrame)
    junk_removed: pd.DataFrame = field(default_factory=pd.DataFrame)
    refunds_absorbed: pd.DataFrame = field(default_factory=pd.DataFrame)
    fully_refunded: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def removed_count(self) -> int:
        return (
            len(self.autopay_removed)
            + len(self.duplicates_removed)
            + len(self.junk_removed)
            + len(self.refunds_absorbed)
            + len(self.fully_refunded)
        )


def clean_description(description: str) -> str:
    text = EMBEDDED_DATE_PREFIX.sub("", str(description).strip())
    return re.sub(r"\s+", " ", text).strip()


def clean_descriptions(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["description"] = result["description"].map(clean_description)
    return result


def _is_autopay(description: str) -> bool:
    lowered = description.lower()
    return any(pattern in lowered for pattern in AUTOPAY_PATTERNS)


def remove_autopay(df: pd.DataFrame) -> pd.DataFrame:
    mask = df["description"].map(_is_autopay)
    return df[~mask].reset_index(drop=True)


def net_partial_refunds(
    df: pd.DataFrame,
    *,
    merchant_col: str = "merchant",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Remove charge/credit rows whose amounts match exactly (ignores merchant name).
    """
    if df.empty:
        empty = df.iloc[0:0].copy()
        return df, empty, empty

    working = df.copy().reset_index(drop=True)
    working["_sort_charge_first"] = (working["amount"] <= 0).astype(int)
    working = working.sort_values(["date", "_sort_charge_first"], kind="stable").drop(
        columns=["_sort_charge_first"]
    )

    drop_indices: set[int] = set()
    absorbed_rows: list[dict] = []
    fully_refunded_rows: list[dict] = []
    debit_pool: dict[float, list[tuple[int, pd.Timestamp]]] = {}

    for idx, row in working.iterrows():
        amount = round(float(row["amount"]), 2)
        if amount > 0:
            debit_pool.setdefault(amount, []).append((idx, pd.Timestamp(row["date"])))
            continue
        if amount >= 0:
            continue

        credit_amount = abs(amount)
        credit_date = pd.Timestamp(row["date"])
        pool = debit_pool.get(credit_amount, [])
        match_i = next(
            (i for i, (_, debit_date) in enumerate(pool) if debit_date <= credit_date),
            None,
        )
        if match_i is None:
            continue

        debit_idx, _ = pool.pop(match_i)
        drop_indices.add(debit_idx)
        drop_indices.add(idx)
        debit_row = working.loc[debit_idx]
        pair_reason = f"Exact amount pair (${credit_amount:.2f})"
        fully_refunded_rows.append(
            {
                "date": debit_row["date"],
                "description": debit_row["description"],
                "merchant": debit_row.get(merchant_col, ""),
                "amount": debit_row["amount"],
                "reason": pair_reason,
            }
        )
        absorbed_rows.append(
            {
                "date": row["date"],
                "description": row["description"],
                "merchant": row.get(merchant_col, ""),
                "amount": row["amount"],
                "reason": pair_reason,
            }
        )

    if not drop_indices:
        return working, pd.DataFrame(absorbed_rows), pd.DataFrame(fully_refunded_rows)

    result = working.drop(index=list(drop_indices)).reset_index(drop=True)
    return result, pd.DataFrame(absorbed_rows), pd.DataFrame(fully_refunded_rows)


def apply_transaction_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Light pre-processing before merchant resolution."""
    result = clean_descriptions(df)
    result = remove_autopay(result)
    return result.reset_index(drop=True)


def apply_transaction_filters_with_audit(df: pd.DataFrame) -> tuple[pd.DataFrame, FilterAudit]:
    audit = FilterAudit(raw_count=len(df))
    result = clean_descriptions(df)

    autopay_mask = result["description"].map(_is_autopay)
    audit.autopay_removed = result[autopay_mask].copy()
    result = result[~autopay_mask]

    dup_mask = result.duplicated(subset=["date", "description", "amount"], keep="first")
    audit.duplicates_removed = result[dup_mask].copy()
    result = result[~dup_mask]

    return result.reset_index(drop=True), audit
