"""Extract transactions from credit card statement PDFs."""

from __future__ import annotations

import re
from collections import defaultdict

import fitz
import pandas as pd

from parser import (
    AMOUNT_COLUMNS,
    DATE_COLUMNS,
    DESC_COLUMNS,
    _detect_header_row,
    _normalize_header,
    _parse_amount,
    _parse_date,
    transactions_from_dataframe,
)

DATE_TOKEN = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")
DATE_INLINE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b")
MONTH_DATE_INLINE = re.compile(
    r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4})\b",
    re.IGNORECASE,
)
AMOUNT_TOKEN = re.compile(r"^[\(-]?\$?[\d,]+\.\d{2}\)?$")
DAILY_CASH_PCT = re.compile(r"^\d+(\.\d+)?%$")

SKIP_LINE_KEYWORDS = (
    "page ",
    "statement period",
    "account number",
    "payment due",
    "minimum payment",
    "new balance",
    "previous balance",
    "credit limit",
    "annual percentage",
    "interest charge",
    "fees charged",
    "apple card customer",
    "goldman sachs",
    "customer name",
    "billing cycle",
    "total payments and credits",
    "total new charges",
    "payments and credits",
    "cardless",
    "member fdic",
)

SECTION_HEADERS = {
    "transactions",
    "payments",
    "interest charged",
    "daily cash",
    "total daily cash",
    "total charges",
    "total payments",
}


def _table_looks_like_transactions(header: list[str]) -> bool:
    normalized = [_normalize_header(cell) for cell in header]
    has_date = any(col in normalized for col in DATE_COLUMNS)
    has_amount = any(col in normalized for col in AMOUNT_COLUMNS)
    has_desc = any(col in normalized for col in DESC_COLUMNS)
    return has_date and has_amount and has_desc


def _transactions_from_table_df(table_df: pd.DataFrame, source_name: str) -> pd.DataFrame | None:
    if table_df.empty or len(table_df) < 2:
        return None
    raw = table_df.astype(str).replace({"nan": "", "None": ""})
    header_row = _detect_header_row(raw)
    header = [_normalize_header(v) for v in raw.iloc[header_row].tolist()]
    if not _table_looks_like_transactions(header):
        return None
    body = raw.iloc[header_row + 1 :].copy()
    body.columns = [str(c).strip() for c in raw.iloc[header_row].tolist()]
    try:
        return transactions_from_dataframe(body, source_name)
    except ValueError:
        return None


def _transactions_from_pdf_tables(doc: fitz.Document, source_name: str) -> pd.DataFrame | None:
    frames: list[pd.DataFrame] = []
    for page in doc:
        finder = page.find_tables()
        if not finder.tables:
            continue
        for table in finder.tables:
            try:
                table_df = table.to_pandas()
            except Exception:
                continue
            parsed = _transactions_from_table_df(table_df, source_name)
            if parsed is not None and not parsed.empty:
                frames.append(parsed)
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def _reconstruct_lines(doc: fitz.Document) -> list[str]:
    """Rebuild reading-order lines from word positions (handles columnar PDF layouts)."""
    lines: list[str] = []
    for page in doc:
        words = page.get_text("words")
        if not words:
            text = page.get_text() or ""
            lines.extend(text.splitlines())
            continue

        grouped: dict[float, list[tuple[float, str]]] = defaultdict(list)
        for x0, y0, _x1, _y1, word, _block, _line, _word_no in words:
            grouped[round(y0, 1)].append((x0, word))

        for _y in sorted(grouped.keys()):
            parts = [word for _x, word in sorted(grouped[_y], key=lambda item: item[0])]
            line = " ".join(parts).strip()
            if line:
                lines.append(line)
    return lines


def _is_address_continuation(line: str) -> bool:
    lowered = f" {line.lower()} "
    if re.search(r"\b\d{5}\b", line) and " usa" in lowered:
        return True
    return False


def _should_skip_line(line: str) -> bool:
    lowered = line.lower().strip()
    if not lowered:
        return True
    if lowered in SECTION_HEADERS:
        return True
    if len(lowered) < 8 and lowered.replace(" ", "") in {"date", "amount", "description"}:
        return True
    return any(keyword in lowered for keyword in SKIP_LINE_KEYWORDS)


def _looks_like_amount(token: str) -> bool:
    return bool(AMOUNT_TOKEN.match(token.strip()))


def _parse_apple_card_style_line(line: str, source_name: str) -> dict | None:
    """
    Parse Apple Card / Goldman Sachs lines:
    MM/DD/YYYY  MERCHANT ...  2%  $1.29  $64.31
    """
    parts = line.split()
    if len(parts) < 3 or not DATE_TOKEN.match(parts[0]):
        return None

    date = _parse_date(parts[0])
    amount = _parse_amount(parts[-1])
    if date is None or amount is None:
        return None

    tail = 1
    if (
        len(parts) >= 5
        and DAILY_CASH_PCT.match(parts[-3])
        and _looks_like_amount(parts[-2])
        and _looks_like_amount(parts[-1])
    ):
        tail = 3

    description = " ".join(parts[1:-tail]).strip()
    if not description or description.lower() in SECTION_HEADERS:
        return None

    return {
        "date": date,
        "description": description,
        "amount": amount,
        "category": "",
        "source_file": source_name,
    }


def _parse_dated_amount_line(line: str, date_match: re.Match[str], source_name: str) -> dict | None:
    """Parse a line with a known date match, description, and trailing amount."""
    date = _parse_date(date_match.group(1))
    if date is None:
        return None

    tokens = line[date_match.end() :].split()
    amount = None
    amount_idx = None
    for idx in range(len(tokens) - 1, -1, -1):
        if _looks_like_amount(tokens[idx]):
            amount = _parse_amount(tokens[idx])
            amount_idx = idx
            break
    if amount is None or amount_idx is None:
        return None

    description = " ".join(tokens[:amount_idx]).strip()
    if not description or len(description) < 2:
        return None

    return {
        "date": date,
        "description": description,
        "amount": amount,
        "category": "",
        "source_file": source_name,
    }


def _parse_loose_date_line(line: str, source_name: str) -> dict | None:
    """Parse lines where date is followed by text and a trailing amount."""
    match = DATE_INLINE.search(line)
    if match:
        return _parse_dated_amount_line(line, match, source_name)

    match = MONTH_DATE_INLINE.search(line)
    if match:
        return _parse_dated_amount_line(line, match, source_name)

    return None


def _transactions_from_lines(lines: list[str], source_name: str) -> pd.DataFrame | None:
    rows: list[dict] = []
    for line in lines:
        text = re.sub(r"\s+", " ", line.strip())
        if not text or _should_skip_line(text) or _is_address_continuation(text):
            continue

        row = _parse_apple_card_style_line(text, source_name)
        if row is None:
            row = _parse_loose_date_line(text, source_name)
        if row:
            rows.append(row)

    if not rows:
        return None
    return pd.DataFrame(rows)


def _transactions_from_full_text_scan(text: str, source_name: str) -> pd.DataFrame | None:
    """Last-resort scan for date ... amount patterns anywhere in the document."""
    pattern = re.compile(
        r"(\d{1,2}/\d{1,2}/\d{2,4}|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4})\s+"
        r"(.+?)\s+"
        r"([\(-]?\$?[\d,]+\.\d{2}\)?)",
        re.MULTILINE | re.IGNORECASE,
    )
    rows = []
    for match in pattern.finditer(text):
        date = _parse_date(match.group(1))
        amount = _parse_amount(match.group(3))
        description = match.group(2).strip()
        if date is None or amount is None or not description:
            continue
        if _should_skip_line(description):
            continue
        if DAILY_CASH_PCT.match(description.split()[-1]):
            continue
        rows.append(
            {
                "date": date,
                "description": description,
                "amount": amount,
                "category": "",
                "source_file": source_name,
            }
        )
    if not rows:
        return None
    return pd.DataFrame(rows)


def extract_pdf_debug_text(content: bytes, max_chars: int = 2500) -> str:
    """Return a text preview from a PDF for troubleshooting failed parses."""
    doc = fitz.open(stream=content, filetype="pdf")
    try:
        chunks: list[str] = []
        for page in doc:
            chunks.append(page.get_text() or "")
            if sum(len(c) for c in chunks) >= max_chars:
                break
        preview = "\n".join(chunks)
        return preview[:max_chars]
    finally:
        doc.close()


def _is_amex_statement(doc: fitz.Document) -> bool:
    sample = " ".join((doc[i].get_text() or "") for i in range(min(2, doc.page_count))).lower()
    return "americanexpress" in sample or "american express" in sample or "platinum card" in sample


def parse_statement_pdf(content: bytes, source_name: str) -> pd.DataFrame:
    """Return normalized transactions extracted from a statement PDF."""
    doc = fitz.open(stream=content, filetype="pdf")
    try:
        if doc.page_count == 0:
            raise ValueError(f"PDF '{source_name}' has no pages.")

        from amex_parser import extract_amex_transactions

        lines = _reconstruct_lines(doc)
        full_text = "\n".join(lines)

        if _is_amex_statement(doc):
            strategies = [extract_amex_transactions(doc, source_name)]
        else:
            from_tables = _transactions_from_pdf_tables(doc, source_name)
            from_lines = _transactions_from_lines(lines, source_name)
            if from_lines is not None and not from_lines.empty:
                strategies = [from_lines]
            elif from_tables is not None and not from_tables.empty:
                strategies = [from_tables]
            else:
                strategies = [_transactions_from_full_text_scan(full_text, source_name)]

        candidates = [df for df in strategies if df is not None and not df.empty]
        if not candidates:
            raise ValueError(
                f"Could not extract transactions from PDF '{source_name}'. "
                "The PDF may be scanned/image-only, password-protected, or use an unsupported layout. "
                "Try exporting CSV from your bank."
            )

        combined = pd.concat(candidates, ignore_index=True)
        combined = combined.drop_duplicates(subset=["date", "description", "amount"], keep="first")
        if combined.empty:
            raise ValueError(f"No valid transactions found in PDF '{source_name}'.")
        return combined
    finally:
        doc.close()
