"""Clean raw statement descriptions into readable merchant names."""

from __future__ import annotations

import re

# (regex on full description or merchant, display name, category)
KNOWN_BRANDS: list[tuple[re.Pattern[str], str, str | None]] = [
    (re.compile(r"amazon|amzn\.com|amz\*|pay\.amazon|amazon\s+marketplace", re.I), "Amazon", "Shopping"),
    (re.compile(r"wal[-\s]?mart|walmart\.com", re.I), "Walmart", "Groceries"),
    (re.compile(r"walgreens", re.I), "Walgreens", "Healthcare"),
    (re.compile(r"publix", re.I), "Publix", "Groceries"),
    (re.compile(r"desi\s*district|tst\*desi|desi\s*dis", re.I), "Desi District", "Dining"),
    (re.compile(r"eractoll|e-zpass|ezpass|cfx\s*-\s*e-pass", re.I), "Toll", "Transport"),
    (re.compile(r"samsclub|sam'?s\s*club", re.I), "Sam's Club", "Groceries"),
    (re.compile(r"7[\s-]?eleven", re.I), "7-Eleven", "Transport"),
    (re.compile(r"oates\s+energy", re.I), "Oates Energy", "Utilities"),
    (re.compile(r"womencare", re.I), "WomenCare", "Healthcare"),
    (re.compile(r"fishhawk\s+sporting", re.I), "Fishhawk Sporting Clays", "Entertainment"),
    (re.compile(r"knockouts\s+hair", re.I), "Knockouts", "Other"),
    (re.compile(r"hometeam|wwp\*hometeam", re.I), "Hometeam", "Other"),
    (re.compile(r"\bwhop\b", re.I), "Whop", "Other"),
    (re.compile(r"return\s+protection\s+benefit", re.I), "Return Protection Benefit", "Other"),
    (re.compile(r"riverview\s+ops", re.I), "Riverview Ops", "Other"),
    (re.compile(r"panera\s+bread|panera", re.I), "Panera Bread", "Dining"),
    (re.compile(r"taco\s+bell", re.I), "Taco Bell", "Dining"),
    (re.compile(r"chipotle", re.I), "Chipotle", "Dining"),
    (re.compile(r"chick-fil-a|chick fil a", re.I), "Chick-fil-A", "Dining"),
    (re.compile(r"subway", re.I), "Subway", "Dining"),
    (re.compile(r"unique\s+india\s+grocery", re.I), "Unique India Grocery", "Groceries"),
    (re.compile(r"jcpenney|jcp", re.I), "JCPenney", "Shopping"),
    (re.compile(r"disney\s*\+|disney\s*plus|disneyplus", re.I), "Disney+", "Subscriptions"),
    (re.compile(r"^nike\b|\bnike\s+retail", re.I), "Nike", "Shopping"),
    (re.compile(r"homedepot|home\s*depo", re.I), "Home Depot", "Shopping"),
    (re.compile(r"lowe'?s", re.I), "Lowe's", "Shopping"),
    (re.compile(r"buffalo\s+wild\s+wings|bww\b", re.I), "Buffalo Wild Wings", "Dining"),
    (re.compile(r"tiktok", re.I), "TikTok", "Shopping"),
    (re.compile(r"taaza\s*mat", re.I), "Taaza Mart", "Groceries"),
    (re.compile(r"india'?s?\s+grill|indias\s+grill", re.I), "India's Grill", "Dining"),
    (re.compile(r"token\s+ramen|kung\s+tea", re.I), "Token Ramen & Kung Tea", "Dining"),
    (re.compile(r"first\s+watch", re.I), "First Watch", "Dining"),
    (re.compile(r"dave'?s?\s+hot\s+chicken", re.I), "Dave's Hot Chicken", "Dining"),
    (re.compile(r"bloody\s+good\s+food", re.I), "Bloody Good Food", "Dining"),
    (re.compile(r"paris\s+baguette", re.I), "Paris Baguette", "Dining"),
    (re.compile(r"portillo", re.I), "Portillo's", "Dining"),
    (re.compile(r"total\s+wine", re.I), "Total Wine & More", "Groceries"),
    (re.compile(r"kohl'?s", re.I), "Kohl's", "Shopping"),
    (re.compile(r"carter'?s", re.I), "Carter's", "Shopping"),
    (re.compile(r"u-?haul", re.I), "U-Haul", "Transport"),
    (re.compile(r"american\s+airl", re.I), "American Airlines", "Travel"),
    (re.compile(r"sprouts\s+farmers", re.I), "Sprouts Farmers Market", "Groceries"),
    (re.compile(r"racetrac", re.I), "RaceTrac", "Transport"),
    (re.compile(r"quest\s+diagnostics", re.I), "Quest Diagnostics", "Healthcare"),
    (re.compile(r"progressive(?!\s+field)", re.I), "Progressive", "Transport"),
    (re.compile(r"cali\s+coffee|ciccio\s+cali", re.I), "Ciccio Cali", "Dining"),
    (re.compile(r"levoit", re.I), "Levoit", "Shopping"),
    (re.compile(r"lululemon", re.I), "Lululemon", "Shopping"),
    (re.compile(r"dollar\s*tree", re.I), "Dollar Tree", "Shopping"),
    (re.compile(r"wayfair", re.I), "Wayfair", "Shopping"),
    (re.compile(r"enterprise\s+rent|\benterprise\b", re.I), "Enterprise", "Travel"),
    (re.compile(r"gladesong\s+commun", re.I), "Gladesong Community", "Utilities"),
    (re.compile(r"license\s*/\s*tag\s*/\s*asm|licensetagasm|pmt\*?\s*fl\s+license", re.I), "FL License/Tag", "Other"),
    (re.compile(r"pirate\s*ship|bt\*pirate", re.I), "Pirate Ship", "Other"),
    (re.compile(r"paypal\s*\*?\s*itaxp", re.I), "PayPal iTax", "Other"),
    (re.compile(r"stars\s+n\b", re.I), "Stars N", "Other"),
    (re.compile(r"colvin\s+inspection", re.I), "Colvin Inspections", "Other"),
    (re.compile(r"mercury\s+auto|mercury\b", re.I), "Mercury Insurance", "Transport"),
    (re.compile(r"the\s+ups\s+store|ups\s+store", re.I), "UPS Store", "Other"),
    (re.compile(r"tplink|tp\s*link", re.I), "TP-Link", "Shopping"),
    (re.compile(r"wmt\s+plus|walmart\+", re.I), "Walmart+", "Subscriptions"),
    (re.compile(r"harbor\s+frei", re.I), "Harbor Freight", "Shopping"),
    (re.compile(r"macys|macy'?s", re.I), "Macy's", "Shopping"),
    (re.compile(r"tonyzfadez", re.I), "Tonyzfadez", "Other"),
    (re.compile(r"spirit\s+al|spirit\s+air", re.I), "Spirit Airlines", "Travel"),
    (re.compile(r"news\s*link|newslink", re.I), "News Link", "Other"),
]

# Prefix keys on merchant_group_key -> (display name, category)
CHAIN_ALIASES: list[tuple[str, str, str]] = [
    ("homedepot", "Home Depot", "Shopping"),
    ("lowes", "Lowe's", "Shopping"),
    ("samsclub", "Sam's Club", "Groceries"),
    ("publix", "Publix", "Groceries"),
    ("buffalowildwings", "Buffalo Wild Wings", "Dining"),
    ("tiktok", "TikTok", "Shopping"),
    ("taazamart", "Taaza Mart", "Groceries"),
    ("indiasgrill", "India's Grill", "Dining"),
    ("tokenramen", "Token Ramen & Kung Tea", "Dining"),
    ("firstwatch", "First Watch", "Dining"),
    ("daveshotchicken", "Dave's Hot Chicken", "Dining"),
    ("totalwine", "Total Wine & More", "Groceries"),
    ("kohls", "Kohl's", "Shopping"),
    ("carters", "Carter's", "Shopping"),
    ("uhaul", "U-Haul", "Transport"),
    ("americanairl", "American Airlines", "Travel"),
    ("sproutsfarmersmarket", "Sprouts Farmers Market", "Groceries"),
    ("parisbaguette", "Paris Baguette", "Dining"),
    ("walmart", "Walmart", "Groceries"),
    ("jcpenney", "JCPenney", "Shopping"),
    ("chickfila", "Chick-fil-A", "Dining"),
    ("panerabread", "Panera Bread", "Dining"),
    ("disney", "Disney+", "Subscriptions"),
    ("disneyplus", "Disney+", "Subscriptions"),
    ("enterprise", "Enterprise", "Travel"),
    ("gladesongcommunit", "Gladesong Community", "Utilities"),
    ("licensetagasm", "FL License/Tag", "Other"),
    ("pirateship", "Pirate Ship", "Other"),
    ("paypalitaxp", "PayPal iTax", "Other"),
    ("starsn", "Stars N", "Other"),
    ("colvininspections", "Colvin Inspections", "Other"),
    ("mercury", "Mercury Insurance", "Transport"),
    ("upsstore", "UPS Store", "Other"),
    ("tplink", "TP-Link", "Shopping"),
    ("tplinkus", "TP-Link", "Shopping"),
    ("desidis", "Desi District", "Dining"),
    ("hometeam", "Hometeam", "Other"),
    ("knockouts", "Knockouts", "Other"),
    ("whop", "Whop", "Other"),
    ("returnprotectionbenefit", "Return Protection Benefit", "Other"),
    ("wmtplus", "Walmart+", "Subscriptions"),
    ("walmartplus", "Walmart+", "Subscriptions"),
    ("harborfreight", "Harbor Freight", "Shopping"),
    ("macys", "Macy's", "Shopping"),
    ("tonyzfadez", "Tonyzfadez", "Other"),
    ("spirital", "Spirit Airlines", "Travel"),
    ("spiritairlines", "Spirit Airlines", "Travel"),
    ("7eleven", "7-Eleven", "Transport"),
    ("newslink", "News Link", "Other"),
]

NAME_CATEGORY_HINTS: list[tuple[str, list[str]]] = [
    ("Dining", [
        "grill", "wings", "ramen", "coffee", "kitchen", "bistro", "chicken", "cafe", "tea",
        "baguette", "custard", "tavola", "rasoi", "chowrastha", "cuisine", "diner", "brunch",
        "bakery", "eatery", "food", "bbq", "sushi", "pizza", "taco", "wok", "deli", "cantina",
        "watch", "portillo", "calibrandon",
    ]),
    ("Groceries", [
        "mart", "grocery", "supermarket", "sprouts", "winemore", "farmersmarket", "spicehub",
    ]),
    ("Shopping", ["depot", "kohls", "carters", "levoit", "lululemon", "dollartree", "wayfair"]),
    ("Transport", ["uhaul", "racetrac", "progressive", "autogw"]),
    ("Travel", ["airline", "airways", "airl", "spirit"]),
    ("Healthcare", ["diagnostics", "quest"]),
]

PREFIX_PATTERN = re.compile(
    r"^(?:AplPay|TST\*|PB\s*\*+|WWP\*|AMZ\*|PHR\*|BPS\*|ERACTOLL|AMAZON MARKETPLACE|BT\*|PMT\*|SP\s+)\s*",
    re.IGNORECASE,
)
STORE_NUMBER = re.compile(r"#\s*\d+")
PHONE_PATTERN = re.compile(r"\s+\d{3}[-.\s]?\d{3}[-.\s]?\d{4}.*$")
EMBEDDED_PHONE = re.compile(r"(\.com|airl|autogw|addre)\d{3}[-.\s]?\d{3}.*$", re.IGNORECASE)
PHONE_INLINE = re.compile(r"\d{3}[-.\s]?\d{3}[-.\s]?\d{4}")
ZIP_SUFFIX = re.compile(r"\s+\d{5}(\s+[A-Z]{2})?(\s+USA)?$", re.IGNORECASE)
CITY_STATE_SUFFIX = re.compile(r"\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s+[A-Z]{2}$")
TRAILING_STATE = re.compile(r"\s+(?:WA|AR|FL|TX|CA|NY|AZ|IN|MA|OR|GA|IL|USA)\s*$", re.IGNORECASE)
DIGIT_BLOB = re.compile(r"\s+\d{4,}.*$")
JUNK_MERCHANT = re.compile(r"^[a-z0-9]{4,10}$", re.IGNORECASE)


def resolve_brand(text: str) -> tuple[str, str | None] | None:
    """Match known brands from the raw statement description or merchant name."""
    for pattern, display, category in KNOWN_BRANDS:
        if pattern.search(text):
            return display, category
    return None


def infer_category_from_name(merchant: str) -> str | None:
    key = merchant_group_key(merchant)
    if not key:
        return None
    for prefix, _, category in CHAIN_ALIASES:
        if key.startswith(prefix) or prefix in key:
            return category
    for category, signals in NAME_CATEGORY_HINTS:
        for signal in signals:
            if signal in key:
                if signal == "mart" and any(
                    skip in key for skip in ("walmart", "taazamart", "dollartree")
                ):
                    continue
                if signal == "food" and "good" in key:
                    return "Dining"
                return category
    return None


def canonicalize_merchant(merchant: str, description: str = "") -> tuple[str, str | None]:
    """Map statement variants to a single display name and category."""
    combined = f"{description} {merchant}"
    brand = resolve_brand(combined)
    if brand:
        return brand

    cleaned = clean_merchant_name(merchant, skip_brand=True)
    key = merchant_group_key(cleaned)
    for prefix, display, category in CHAIN_ALIASES:
        if key.startswith(prefix) or prefix in key:
            return display, category

    from_name = infer_category_from_name(cleaned)
    return cleaned, from_name


def _title_words(text: str) -> str:
    words = text.split()
    titled = []
    for word in words:
        lower = word.lower()
        if lower in {"llc", "inc", "co"}:
            titled.append(word.upper())
        elif re.fullmatch(r"[a-z]{2}", lower):
            continue
        elif word.isupper() and len(word) <= 4 and any(ch.isdigit() for ch in word):
            titled.append(word)
        else:
            titled.append(word.capitalize() if word.isupper() else word.title())
    return " ".join(titled).strip()


def clean_merchant_name(description: str, *, skip_brand: bool = False) -> str:
    """Strip prefixes, addresses, and store numbers from a statement description."""
    if not skip_brand:
        brand = resolve_brand(description)
        if brand:
            return brand[0]

    text = re.sub(r"\s+", " ", description.strip())
    text = PREFIX_PATTERN.sub("", text)
    text = EMBEDDED_PHONE.sub("", text)
    text = PHONE_INLINE.sub("", text)
    text = STORE_NUMBER.sub("", text)
    text = PHONE_PATTERN.sub("", text)
    text = ZIP_SUFFIX.sub("", text)
    text = CITY_STATE_SUFFIX.sub("", text)
    text = TRAILING_STATE.sub("", text)
    text = DIGIT_BLOB.sub("", text)
    text = re.sub(r"\.com$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" ,-*")

    if not text:
        return description.strip()

    tokens = [t for t in text.split() if t.lower() not in {"na", "pa", "wa", "ar", "fl", "usa", "tx", "nc", "ca", "in"}]
    text = " ".join(tokens[:5] if len(tokens) > 6 else tokens)

    return _title_words(text) if text else description.strip()


def merchant_group_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def is_junk_merchant(merchant: str, description: str) -> bool:
    """Drop parsed fragments that are not real merchants (e.g. toll reference codes)."""
    name = merchant.strip()
    if not name:
        return True
    if resolve_brand(description) or resolve_brand(name):
        return False
    if JUNK_MERCHANT.fullmatch(name):
        # Alphabetic names like "Mercury" are real merchants, not parse codes like "2ts8b9".
        if name.isalpha():
            return False
        return True
    if name.lower() in {"na pa", "na", "pa", "wa", "ar", "fl", "usa", "the", "tst"}:
        return True
    return False


def merchant_category_hint(description: str) -> str | None:
    brand = resolve_brand(description)
    return brand[1] if brand else None
