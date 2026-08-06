"""
ai/utils.py — Shared utility helpers used across all AI modules.
"""
import re
import os
import uuid
from datetime import datetime


# ── Date Parsing ─────────────────────────────────────────────────────────────

# All date formats we attempt to parse
_DATE_FORMATS = [
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%m/%Y",    "%m-%Y",    "%m.%Y",
    "%d/%m/%y", "%d-%m-%y", "%d.%m.%y",
    "%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d",
    "%b %Y",    "%B %Y",                 # "Jan 2026", "January 2026"
    "%d %b %Y", "%d %B %Y",             # "12 Jan 2026"
    "%Y",                                # year only
]


def parse_date(raw: str) -> str:
    """
    Try to parse a raw date string into DD-MM-YYYY.
    Returns the original string if parsing fails.
    """
    if not raw:
        return "Not Detected"

    raw = raw.strip()

    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
            # If only year parsed, return year string
            if fmt == "%Y":
                return raw
            # If only month+year, return MM-YYYY
            if fmt in ("%m/%Y", "%m-%Y", "%m.%Y"):
                return dt.strftime("%m-%Y")
            return dt.strftime("%d-%m-%Y")
        except ValueError:
            continue

    return raw  # Return as-is if we can't parse


def is_expired(date_str: str) -> bool:
    """
    Return True if date_str represents a date in the past.
    Handles DD-MM-YYYY and MM-YYYY formats.
    """
    if not date_str or date_str in ("Not Detected", ""):
        return False

    try:
        # Try DD-MM-YYYY
        dt = datetime.strptime(date_str, "%d-%m-%Y")
        return dt.date() < datetime.today().date()
    except ValueError:
        pass

    try:
        # Try MM-YYYY (assume last day of month)
        from calendar import monthrange
        dt = datetime.strptime(date_str, "%m-%Y")
        last_day = monthrange(dt.year, dt.month)[1]
        expiry = dt.replace(day=last_day)
        return expiry.date() < datetime.today().date()
    except ValueError:
        pass

    return False


def days_until_expiry(date_str: str) -> int:
    """
    Return the number of days until expiry.
    Negative = already expired. Returns 9999 if unknown.
    """
    if not date_str or date_str == "Not Detected":
        return 9999

    try:
        dt = datetime.strptime(date_str, "%d-%m-%Y")
        delta = dt.date() - datetime.today().date()
        return delta.days
    except ValueError:
        pass

    try:
        from calendar import monthrange
        dt = datetime.strptime(date_str, "%m-%Y")
        last_day = monthrange(dt.year, dt.month)[1]
        expiry = dt.replace(day=last_day)
        delta = expiry.date() - datetime.today().date()
        return delta.days
    except ValueError:
        pass

    return 9999


# ── File Helpers ──────────────────────────────────────────────────────────────

def unique_filename(extension: str = "jpg") -> str:
    """Generate a UUID-based filename."""
    return f"{uuid.uuid4().hex}.{extension}"


def safe_makedirs(path: str) -> None:
    """Create directory tree if it does not exist."""
    os.makedirs(path, exist_ok=True)


# ── Text Cleaning ─────────────────────────────────────────────────────────────

def clean_ocr_text(text: str) -> str:
    """Collapse whitespace and strip common OCR artefacts."""
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text
