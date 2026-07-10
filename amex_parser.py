"""American Express statement PDF extraction."""

from __future__ import annotations

import re
from collections import defaultdict

import fitz
import pandas as pd

from parser import _parse_amount, _parse_date

AMEX_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{2}\*?$")
AMEX_AMOUNT_RE = re.compile(r"^[\(-]?\$[\d,]+\.\d{2}$")

DATE_X_MAX = 85.0
AMOUNT_X_MIN = 470.0

SKIP_DESC = {
    "payments",
    "credits",
    "new charges",
    "fees",
    "detail",
    "detail continued",
    "amount",
    "summary",
    "pay in full",
    "pay over time",
    "total",
    "total payments",
    "total new charges",
    "total fees",
    "total payments and credits",
    "continued on reverse",
    "continued on next page",
    "continued",
    "and credits",
    "and/or cash advance activity",
    "- pay over time and/or cash advance activity",
    "*indicates posting date",
}

SKIP_DESC_PREFIXES = (
    "total ",
    "pay ",
    "p. ",
)


def _is_amount_token(token: str) -> bool:
    cleaned = token.replace("⧫", "").strip()
    return bool(AMEX_AMOUNT_RE.match(cleaned))


def _is_date_token(token: str) -> bool:
    return bool(AMEX_DATE_RE.match(token.strip()))


def _clean_date_token(token: str) -> str:
    return token.strip().rstrip("*")


def _row_buckets(words: list[tuple[float, str]]) -> tuple[list[str], list[str], list[str]]:
    left, mid, right = [], [], []
    for x, word in sorted(words, key=lambda item: item[0]):
        if word == "⧫":
            continue
        if x < DATE_X_MAX:
            left.append(word)
        elif x >= AMOUNT_X_MIN:
            right.append(word)
        else:
            mid.append(word)
    return left, mid, right


def _desc_text(mid: list[str]) -> str:
    text = " ".join(mid).strip()
    return re.sub(r"\s+", " ", text)


CATEGORY_LINES = {
    "merchandise",
    "book stores",
    "department store",
    "discount store",
}


def _is_junk_description(text: str) -> bool:
    stripped = text.strip()
    if re.fullmatch(r"Y{4,}", stripped, re.IGNORECASE):
        return True
    if re.fullmatch(r"X{4,}", stripped, re.IGNORECASE):
        return True
    return False


def _is_continuation_line(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return True
    if lowered in CATEGORY_LINES:
        return True
    if re.fullmatch(r"[\d\s\-+/.@]+", lowered):
        return True
    if re.search(r"\d{3}[-\s]?\d{3}[-\s]?\d{4}", lowered) and len(lowered) < 40:
        return True
    return False


def _is_noise_desc(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return True
    if lowered in SKIP_DESC:
        return True
    if any(lowered.startswith(prefix) for prefix in SKIP_DESC_PREFIXES):
        return True
    if re.fullmatch(r"[a-z]\s+[a-z]+", lowered):
        return True
    if lowered.startswith("account ending"):
        return True
    if lowered.startswith("card ending"):
        return True
    if re.search(r"ending \d", lowered):
        return True
    if lowered.startswith("b mandadapu"):
        return True
    if "continued on" in lowered:
        return True
    if re.fullmatch(r"p\. \d+/\d+", lowered):
        return True
    if "pay over time" in lowered:
        return True
    if re.search(r"\$0\.00.*\$[\d,]+\.\d{2}", lowered):
        return True
    return False


def _amount_from_tokens(tokens: list[str]) -> float | None:
    for token in tokens:
        if _is_amount_token(token):
            return _parse_amount(token)
    return None


def _parse_amex_rows(rows: list[tuple[float, list[tuple[float, str]]]], source_name: str) -> list[dict]:
    parsed_rows: list[dict] = []
    desc_buffer: list[str] = []
    i = 0

    section_markers = {"payments", "credits", "new charges", "fees"}

    while i < len(rows):
        _y, words = rows[i]
        left, mid, right = _row_buckets(words)
        date_token = next((t for t in left if _is_date_token(t)), None)

        if not date_token:
            desc = _desc_text(mid)
            left_text = " ".join(left).lower().strip()
            if left_text in section_markers or left_text.startswith("total"):
                desc_buffer = []
            elif desc and _is_noise_desc(desc):
                if _is_continuation_line(desc):
                    pass
                else:
                    desc_buffer = []
            elif desc and not _is_continuation_line(desc) and not _is_junk_description(desc):
                desc_buffer.append(desc)
            i += 1
            continue

        date = _parse_date(_clean_date_token(date_token))
        if date is None:
            i += 1
            continue

        amount = _amount_from_tokens(right)
        amount_row_idx = i

        if amount is None:
            for j in range(i + 1, min(i + 4, len(rows))):
                _ny, nwords = rows[j]
                _, _, nright = _row_buckets(nwords)
                nleft, _, _ = _row_buckets(nwords)
                if any(_is_date_token(t) for t in nleft):
                    break
                candidate = _amount_from_tokens(nright)
                if candidate is not None:
                    amount = candidate
                    amount_row_idx = j
                    break

        if amount is None:
            desc_buffer = []
            i += 1
            continue

        description_parts = list(desc_buffer)
        same_row_desc = _desc_text(mid)
        if same_row_desc and not _is_noise_desc(same_row_desc):
            description_parts.append(same_row_desc)

        for j in range(i + 1, amount_row_idx):
            _iy, iwords = rows[j]
            _, imid, iright = _row_buckets(iwords)
            ileft, _, _ = _row_buckets(iwords)
            if any(_is_date_token(t) for t in ileft):
                break
            if _amount_from_tokens(iright) is not None:
                continue
            desc = _desc_text(imid)
            if desc and not _is_noise_desc(desc):
                description_parts.append(desc)

        primary_parts = [
            p for p in description_parts if not _is_continuation_line(p) and not _is_junk_description(p)
        ]
        description = primary_parts[-1] if primary_parts else " ".join(description_parts).strip()
        desc_buffer = []

        if description:
            parsed_rows.append(
                {
                    "date": date,
                    "description": description,
                    "amount": amount,
                    "category": "",
                    "source_file": source_name,
                }
            )

        i = amount_row_idx + 1
        while i < len(rows):
            _cy, cwords = rows[i]
            cleft, cmid, cright = _row_buckets(cwords)
            if any(_is_date_token(t) for t in cleft):
                break
            if _amount_from_tokens(cright) is not None:
                break
            cont = _desc_text(cmid)
            if not cont or not _is_continuation_line(cont):
                break
            i += 1

    return parsed_rows


def _page_rows(page: fitz.Page) -> list[tuple[float, list[tuple[float, str]]]]:
    grouped: dict[float, list[tuple[float, str]]] = defaultdict(list)
    for x0, y0, _x1, _y1, word, _block, _line, _wno in page.get_text("words"):
        grouped[round(y0, 1)].append((x0, word))
    return sorted(grouped.items(), key=lambda item: item[0])


def extract_amex_transactions(doc: fitz.Document, source_name: str) -> pd.DataFrame | None:
    """Extract transactions from an American Express statement PDF."""
    all_rows: list[dict] = []
    for page in doc:
        page_rows = _page_rows(page)
        all_rows.extend(_parse_amex_rows(page_rows, source_name))

    if not all_rows:
        return None

    df = pd.DataFrame(all_rows)
    df = df.drop_duplicates(subset=["date", "description", "amount"], keep="first")
    return df
