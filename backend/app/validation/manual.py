"""Validation of values a person types while correcting a record. Pure functions, no database."""
from __future__ import annotations

from datetime import date

from app.validation.dates import normalize_date
from app.validation.israeli_id import normalize_id
from app.validation.numbers import CENTRAL, COMMITMENT, NumberRule
from app.validation.senders import match_sender

SCALAR_FIELDS = ("first_name", "last_name", "id_number", "received_date", "sender")
LIST_RULES: dict[str, NumberRule] = {"central_numbers": CENTRAL, "commitment_numbers": COMMITMENT}


class InvalidValue(ValueError):
    """The typed value is not acceptable; the message is shown to the user."""


def clean_scalar(name: str, new: str | None) -> str | None:
    """Normalize one typed value. An empty value clears the field (returns None)."""
    new = (new or "").strip()
    if not new:
        return None
    if name == "id_number":
        value = normalize_id(new)
        if value is None:
            raise InvalidValue('ת"ז חייבת להכיל בין 5 ל-9 ספרות')
        return value
    if name == "received_date":
        parsed = normalize_date(new)
        if parsed is None:
            raise InvalidValue("תאריך לא תקין")
        if parsed > date.today():
            raise InvalidValue("תאריך בעתיד")
        return parsed.isoformat()
    if name == "sender":
        match = match_sender(new)
        if match is None:
            raise InvalidValue("הגורם השולח אינו ברשימה")
        return match.name
    return new


def clean_list(name: str, values: list[str | None]) -> list[str]:
    """Normalize a typed list, dropping blanks and duplicates."""
    rule = LIST_RULES[name]
    out: list[str] = []
    for raw in values:
        if not (raw or "").strip():
            continue
        value = rule.clean(raw)
        if not rule.is_valid(value):
            raise InvalidValue(rule.input_error)
        if value not in out:
            out.append(value)
    return out
