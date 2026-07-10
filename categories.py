"""Assign spending categories from bank labels or keyword fallback."""

from __future__ import annotations

import re

import pandas as pd

KEYWORD_RULES: list[tuple[str, list[str]]] = [
    ("Groceries", ["whole foods", "trader joe", "kroger", "safeway", "costco", "walmart", "target", "aldi", "publix", "wegmans", "grocery", "india grocery", "sams club", "samsclub", "taaza mart", "sprouts", "total wine"]),
    ("Dining", ["restaurant", "doordash", "uber eats", "grubhub", "starbucks", "mcdonald", "chipotle", "cafe", "pizza", "dining", "taco bell", "panera", "subway", "chick-fil-a", "buffalo wild wings", "grill", "ramen", "first watch", "wings", "kung tea", "baguette", "hot chicken"]),
    ("Transport", ["uber", "lyft", "shell", "chevron", "exxon", "bp ", "parking", "transit", "metro", "gas", "toll", "eractoll", "u-haul", "uhaul", "racetrac", "progressive", "7-eleven", "7 eleven"]),
    ("Travel", ["airline", "hotel", "airbnb", "expedia", "delta", "united", "marriott", "hilton", "booking.com", "american airl", "spirit"]),
    ("Shopping", ["amazon", "ebay", "etsy", "best buy", "apple.com", "nike", "home depot", "homedepot", "lowes", "lowe's", "retail", "jcpenney", "jcp", "tiktok", "kohl", "carter", "levoit", "lululemon", "dollar tree", "wayfair"]),
    ("Subscriptions", ["netflix", "spotify", "hulu", "disney+", "disney plus", "adobe", "microsoft", "google *", "subscription", "membership", "walmart+", "wmt plus"]),
    ("Utilities", ["electric", "water", "internet", "comcast", "verizon", "at&t", "utility", "pg&e", "oates energy", "energy"]),
    ("Healthcare", ["pharmacy", "cvs", "walgreens", "medical", "doctor", "hospital", "dental", "health", "womencare"]),
    ("Entertainment", ["amc", "cinema", "ticket", "steam", "playstation", "xbox", "concert", "museum", "sporting", "fishhawk"]),
    ("Fees & Interest", ["fee", "interest", "late charge", "annual fee", "finance charge"]),
    ("Housing", ["bilt housing", "rent"]),
]

SPEND_CATEGORIES: list[str] = [name for name, _ in KEYWORD_RULES] + ["Other"]


def _normalize_bank_category(category: str) -> str:
    text = category.strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in {"payment", "credit", "autopay", "online payment"}:
        return "Payments"
    if "food" in lowered or "dining" in lowered or "restaurant" in lowered:
        return "Dining"
    if "grocery" in lowered or "groceries" in lowered:
        return "Groceries"
    if "travel" in lowered or "airline" in lowered or "hotel" in lowered:
        return "Travel"
    if "gas" in lowered or "automotive" in lowered or "transport" in lowered:
        return "Transport"
    if "shopping" in lowered or "merchandise" in lowered:
        return "Shopping"
    if "entertainment" in lowered:
        return "Entertainment"
    if "health" in lowered or "medical" in lowered:
        return "Healthcare"
    if "fee" in lowered or "interest" in lowered:
        return "Fees & Interest"
    return text.title()


def categorize_description(description: str) -> str:
    text = description.lower()
    for category, keywords in KEYWORD_RULES:
        for keyword in keywords:
            if keyword in text:
                return category
    return "Other"


def enrich_categories(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Backward-compatible entry point — delegates to merchants.enrich_categories."""
    from merchants import enrich_categories as enrich_with_merchants

    return enrich_with_merchants(df, **kwargs)
