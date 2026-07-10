"""Optional online merchant category lookup with local cache."""

from __future__ import annotations

import json
import re
from pathlib import Path

from categories import SPEND_CATEGORIES
from merchant_cleaner import (
    canonicalize_merchant,
    clean_merchant_name,
    infer_category_from_name,
    merchant_group_key,
)

CACHE_PATH = Path(__file__).resolve().parent / ".cache" / "merchant_lookup.json"
CACHE_VERSION = 2

CATEGORY_SIGNALS: list[tuple[str, list[str]]] = [
    ("Dining", [
        "restaurant", "fast food", "cafe", "coffee", "dining", "pizza", "burger", "taco",
        "grill", "wings", "ramen", "kitchen", "bistro", "eatery", "bakery", "baguette",
        "brunch", "bar and grill", "sports bar", "food delivery", "tripadvisor",
        "yelp", "eat", "diner", "custard", "tea house", "cuisine", "wings. beer",
    ]),
    ("Groceries", [
        "grocery", "supermarket", "food store", "grocer", "farmers market", "convenience store",
        "liquor store", "wine shop", "wine & spirits",
    ]),
    ("Transport", [
        "gas station", "fuel", "toll", "parking", "transit", "uber", "lyft", "moving truck",
        "auto insurance", "car insurance",
    ]),
    ("Utilities", ["utility", "utilities", "energy", "electric", "water", "propane"]),
    ("Healthcare", [
        "pharmacy", "medical", "health", "dental", "clinic", "hospital", "walgreens", "cvs",
        "diagnostics", "laboratory",
    ]),
    ("Shopping", [
        "retail", "department store", "clothing", "apparel", "e-commerce", "marketplace",
        "home improvement", "hardware store", "online shop", "social media", "tiktok shop",
    ]),
    ("Entertainment", ["entertainment", "sporting", "golf", "cinema", "theater", "club"]),
    ("Subscriptions", ["subscription", "streaming", "membership", "saas"]),
    ("Travel", ["hotel", "airline", "travel", "lodging", "flight", "airways"]),
    ("Housing", ["rent", "housing", "apartment", "property management", "hoa", "community"]),
    ("Fees & Interest", ["fee", "interest", "finance charge", "late charge"]),
]


def _infer_category(text: str, merchant: str = "") -> str | None:
    combined = f"{merchant} {text}".lower()
    best_category = None
    best_score = 0
    for category, signals in CATEGORY_SIGNALS:
        score = sum(1 for signal in signals if signal in combined)
        if score > best_score:
            best_score = score
            best_category = category
    if best_category and best_category in SPEND_CATEGORIES and best_score > 0:
        return best_category

    from_name = infer_category_from_name(merchant)
    if from_name:
        return from_name
    return None


def _canonical_from_search(merchant: str, results: list[dict[str, str]]) -> str:
    if not results:
        return merchant
    title = results[0].get("title", "")
    title = re.split(r"[|\-–—]", title)[0].strip()
    title = re.sub(r"\s*-\s*(Tripadvisor|Yelp|Wikipedia).*$", "", title, flags=re.IGNORECASE)
    if not title or len(title) > 80:
        return merchant
    merchant_token = merchant_group_key(merchant)[:6]
    if merchant_token and merchant_token in merchant_group_key(title):
        return title
    return merchant


def _search_web(query: str) -> tuple[str, list[dict[str, str]]]:
    results: list[dict[str, str]] = []
    try:
        from ddgs import DDGS

        results = DDGS().text(query, max_results=5)
    except Exception:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
        except Exception:
            return "", []

    if not results:
        return "", []

    combined_text = " ".join(
        f"{item.get('title', '')} {item.get('body', '')}" for item in results
    )
    return combined_text, results


class MerchantLookupCache:
    def __init__(self, path: Path = CACHE_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict[str, str | int]] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))

    def save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def _category_cache_key(self, merchant: str) -> str:
        return f"cat:{merchant_group_key(merchant)}"

    def lookup_merchant(
        self,
        merchant: str,
        description: str = "",
    ) -> tuple[str, str | None]:
        """Return canonical merchant name and spending category."""
        canonical, category = canonicalize_merchant(merchant, description)
        if category:
            return canonical, category

        from_name = infer_category_from_name(canonical)
        if from_name:
            return canonical, from_name

        key = self._category_cache_key(canonical)
        cached = self._data.get(key)
        if cached and cached.get("v") == CACHE_VERSION:
            cached_category = cached.get("category") or None
            cached_merchant = str(cached.get("merchant") or canonical)
            if cached_category in SPEND_CATEGORIES:
                return cached_merchant, cached_category

        search_name = clean_merchant_name(description) if description else canonical
        queries = [
            f"{search_name} restaurant",
            f"{search_name} store",
            f"{search_name}",
        ]
        combined_text = canonical
        search_results: list[dict[str, str]] = []
        for query in queries:
            combined_text, search_results = _search_web(query)
            if combined_text:
                break

        if search_results:
            canonical = _canonical_from_search(canonical, search_results)
            _, category = canonicalize_merchant(canonical, description)

        if not category:
            category = _infer_category(combined_text, canonical)

        self._data[key] = {
            "merchant": canonical,
            "category": category or "",
            "v": CACHE_VERSION,
        }
        return canonical, category
