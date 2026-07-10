"""User-editable merchant name and category overrides (no code changes needed)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from categories import SPEND_CATEGORIES
from merchant_cleaner import merchant_group_key

RULES_PATH = Path(__file__).resolve().parent / ".cache" / "merchant_rules.json"


def _load_rules() -> dict[str, dict[str, str]]:
    if not RULES_PATH.exists():
        return {}
    try:
        data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data.get("rules", {})


def lookup_rule(merchant: str, description: str = "") -> dict[str, str] | None:
    rules = _load_rules()
    if not rules:
        return None

    from merchant_cleaner import clean_merchant_name

    keys = [merchant_group_key(merchant)]
    if description:
        keys.append(merchant_group_key(clean_merchant_name(description)))

    for key in keys:
        if not key:
            continue
        if key in rules:
            return rules[key]
        for rule_key, rule in rules.items():
            if len(rule_key) >= 5 and key.startswith(rule_key):
                return rule
    return None


def apply_merchant_rules(df: pd.DataFrame) -> pd.DataFrame:
    """Apply local overrides from `.cache/merchant_rules.json`."""
    rules = _load_rules()
    if not rules:
        return df

    result = df.copy()
    for idx, row in result.iterrows():
        rule = lookup_rule(str(row["merchant"]), str(row["description"]))
        if not rule:
            continue
        merchant = rule.get("merchant")
        category = rule.get("category")
        if merchant:
            result.at[idx, "merchant"] = merchant
        if category and category in SPEND_CATEGORIES:
            result.at[idx, "spend_category"] = category
    return result


def ensure_rules_file() -> None:
    """Create an empty rules file with examples if it does not exist."""
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if RULES_PATH.exists():
        return
    RULES_PATH.write_text(
        json.dumps(
            {
                "rules": {},
                "_help": {
                    "key": "merchant_group_key — lowercase letters/digits only, e.g. starbucks",
                    "merchant": "optional display name",
                    "category": f"one of: {', '.join(SPEND_CATEGORIES)}",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
