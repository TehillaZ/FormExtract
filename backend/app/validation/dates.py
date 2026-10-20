"""Date parsing for Israeli forms (day first)."""
from __future__ import annotations

import re
from datetime import date

_DATE_RE = re.compile(r"(\d{1,2})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{2,4})")
_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def normalize_date(raw: str | None) -> date | None:
    """dd/mm/yyyy, dd.mm.yy or dd-mm-yyyy -> date; ISO yyyy-mm-dd is accepted too. None if unparseable."""
    if not raw:
        return None
    raw = raw.strip()
    if _ISO_RE.fullmatch(raw):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None
    m = _DATE_RE.search(raw)
    if not m:
        return None
    d, mo, y = int(m[1]), int(m[2]), int(m[3])
    if y < 100:
        y += 2000
    try:
        return date(y, mo, d)
    except ValueError:
        return None
