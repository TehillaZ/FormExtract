"""Format rules for the two list-valued numbers. One definition, used both when reading a form
(pipeline/extract.py) and when a person types a correction (validation/manual.py)."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class NumberRule:
    clean: Callable[[str | None], str]     # strip noise: "93 93 76" -> "939376"
    is_valid: Callable[[str], bool]
    flag_reason: str                       # shown on a flagged extracted value
    input_error: str                       # returned when a person types an invalid value


CENTRAL = NumberRule(
    clean=lambda s: re.sub(r"\D", "", s or ""),
    is_valid=lambda v: len(v) == 6,
    flag_reason="מספר מרכזי אינו בן 6 ספרות",
    input_error="מספר מרכזי חייב להכיל 6 ספרות",
)

COMMITMENT = NumberRule(
    clean=lambda s: re.sub(r"\s+", "", s or ""),
    is_valid=lambda v: 4 <= len(v) <= 12 and re.fullmatch(r"[A-Za-z]?\d+", v) is not None,
    flag_reason="פורמט מספר התחייבות חריג",
    input_error="מספר התחייבות: 4 עד 12 תווים, אות אופציונלית ואז ספרות",
)
