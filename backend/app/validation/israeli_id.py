"""Israeli ID (teudat zehut) normalization and check-digit validation."""
from __future__ import annotations

import re


def normalize_id(raw: str | None) -> str | None:
    """Keep digits only and left-pad to 9. Returns None when nothing usable is left."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if not 5 <= len(digits) <= 9:
        return None
    return digits.zfill(9)


def id_checksum_ok(id9: str) -> bool:
    if not re.fullmatch(r"\d{9}", id9):
        return False
    total = 0
    for i, ch in enumerate(id9):
        n = int(ch) * (1 if i % 2 == 0 else 2)
        total += n - 9 if n > 9 else n
    return total % 10 == 0
