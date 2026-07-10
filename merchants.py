"""Resolve merchants and spending categories."""

from __future__ import annotations

import pandas as pd

from filters import FilterAudit, net_partial_refunds
from merchant_cleaner import (
    canonicalize_merchant,
    clean_merchant_name,
    is_junk_merchant,
    merchant_category_hint,
    resolve_brand,
)
from merchant_lookup import MerchantLookupCache
from merchant_rules import apply_merchant_rules, ensure_rules_file, lookup_rule


def _skip_online_lookup(merchant: str, description: str) -> bool:
    combined = f"{description} {merchant}"
    brand = resolve_brand(combined)
    if brand and brand[1] == "Other":
        return True
    rule = lookup_rule(merchant, description)
    return bool(rule and rule.get("category") == "Other")


def resolve_merchants(descriptions: pd.Series) -> tuple[pd.Series, pd.Series]:
    merchants: list[str] = []
    categories: list[str | None] = []

    for description in descriptions:
        brand = resolve_brand(description)
        if brand:
            merchant, category = brand
        else:
            merchant = clean_merchant_name(description)
            category = None

        merchant, hinted = canonicalize_merchant(merchant, description)
        if category is None and hinted:
            category = hinted

        if category is None:
            category = merchant_category_hint(description)

        merchants.append(merchant)
        categories.append(category)

    return pd.Series(merchants, index=descriptions.index), pd.Series(categories, index=descriptions.index)


def _auto_categorize_unknown(result: pd.DataFrame) -> pd.DataFrame:
    cache = MerchantLookupCache()
    other_rows = result.index[result["spend_category"] == "Other"]
    for idx in other_rows:
        merchant = str(result.at[idx, "merchant"])
        description = str(result.at[idx, "description"])
        if _skip_online_lookup(merchant, description):
            continue
        merchant, category = cache.lookup_merchant(merchant, description)
        result.at[idx, "merchant"] = merchant
        if category:
            result.at[idx, "spend_category"] = category
    cache.save()
    return result


def enrich_categories(
    df: pd.DataFrame,
    *,
    auto_categorize_unknown: bool = False,
    use_online_lookup: bool = False,
    audit: FilterAudit | None = None,
    net_refunds: bool = False,
) -> pd.DataFrame:
    from categories import _normalize_bank_category, categorize_description

    if use_online_lookup:
        auto_categorize_unknown = True

    ensure_rules_file()
    result = df.copy()
    result["merchant"], lookup_categories = resolve_merchants(result["description"])

    if net_refunds:
        result, absorbed, fully_refunded = net_partial_refunds(result)
        if audit is not None:
            audit.refunds_absorbed = absorbed
            audit.fully_refunded = fully_refunded
        result["merchant"], lookup_categories = resolve_merchants(result["description"])

    bank_categories = result["category"].fillna("").astype(str).map(_normalize_bank_category)
    inferred = result.apply(
        lambda row: categorize_description(f"{row['merchant']} {row['description']}"),
        axis=1,
    )
    fallback = bank_categories.where(bank_categories != "", inferred)

    result["spend_category"] = lookup_categories.where(
        lookup_categories.notna() & (lookup_categories != ""),
        fallback,
    )

    result["is_spending"] = ~result["spend_category"].isin(["Payments"])
    result["spend_amount"] = result["amount"].where(result["is_spending"], 0.0)

    if auto_categorize_unknown:
        result = _auto_categorize_unknown(result)

    result = apply_merchant_rules(result)

    junk_mask = result.apply(
        lambda row: is_junk_merchant(str(row["merchant"]), str(row["description"])),
        axis=1,
    )
    if audit is not None:
        audit.junk_removed = result[junk_mask].copy()

    return result[~junk_mask].reset_index(drop=True)


def finalize_spending(
    df: pd.DataFrame,
    audit: FilterAudit | None = None,
) -> pd.DataFrame:
    """Net refunds on a (date-filtered) subset and compute spend amounts."""
    if df.empty:
        return df.copy()

    result, absorbed, fully_refunded = net_partial_refunds(df)
    if audit is not None:
        audit.refunds_absorbed = absorbed
        audit.fully_refunded = fully_refunded

    result["is_spending"] = ~result["spend_category"].isin(["Payments"])
    result["spend_amount"] = result["amount"].where(result["is_spending"], 0.0)
    return result.reset_index(drop=True)
