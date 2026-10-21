"""Model output -> normalized fields with confidence (PLAN 5.2, 5.3).

Confidence never comes from the model. It comes from checks we can make ourselves: a barcode that matches,
an ID that passes its check digit, an exact sender match, the kind of handwriting, or disagreement between
readings. Anything we cannot verify is at most medium, and a field that was not found is always low.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

from app.config import settings
from app.schemas import CommitmentRecord, Confidence, Field, RawExtraction, RawValue
from app.validation.dates import normalize_date
from app.validation.israeli_id import id_checksum_ok, normalize_id
from app.validation.numbers import CENTRAL, COMMITMENT, NumberRule
from app.validation.senders import match_sender

NOT_FOUND = "לא נמצא"
HANDWRITTEN = "כתב יד"
LOW_QUALITY = "איכות תמונה נמוכה"
AMBIGUOUS_NUMBER = "כמה מספרים אפשריים בטופס"
UNCORROBORATED_ID = "קריאה אחת בלבד, ללא סימון"

__all__ = ["NOT_FOUND", "build_record", "normalize_date"]


def _missing() -> Field:
    return Field(value=None, confidence="low", reasons=[NOT_FOUND])


def _prefer_highlighted(items: list[RawValue]) -> list[RawValue]:
    """The sample forms mark the wanted value with a yellow marker; when any candidate is marked, only those count."""
    marked = [i for i in items if i.highlighted]
    return marked or items


# ---- names --------------------------------------------------------------------------------------

def build_name(rv: RawValue) -> Field:
    value = (rv.value or "").strip()
    if not value:
        return _missing()
    if rv.source == "handwritten":   # cannot be verified, so a person must look
        return Field(value=value, raw_text=rv.value, source=rv.source, confidence="low", reasons=[HANDWRITTEN])
    return Field(value=value, raw_text=rv.value, source=rv.source, confidence="medium")


# ---- ID -----------------------------------------------------------------------------------------

def _id_confidence(checksum_ok: bool, consistent: bool, corroborated: bool) -> tuple[Confidence, list[str]]:
    """strict: the check digit decides, but passing it is not enough to call an ID verified. About one random
    9-digit number in ten passes, and so does the printer's own ID. On the development pages 7 of the 19 IDs that
    passed alone were wrong; all 12 right ones were highlighted. So "verified" also needs corroboration: the same
    ID read at least twice, or the form pointing at it. lenient: the check digit is only information (ADR-014)."""
    if settings.id_checksum_mode == "strict":
        if not checksum_ok:
            return "low", ["ספרת ביקורת לא תקינה"]
        if not consistent:
            return "low", []
        return ("high", []) if corroborated else ("medium", [UNCORROBORATED_ID])
    level: Confidence = "medium" if consistent else "low"
    return level, ([] if checksum_ok else ["ספרת ביקורת לא תקינה (מידע בלבד)"])


def build_id(candidates: list[RawValue]) -> Field:
    candidates = _prefer_highlighted(candidates)
    reads = [(normalize_id(c.value), c) for c in candidates if c.value]
    valid = [(n, c) for n, c in reads if n]
    if not valid:
        raw = next((c.value for _, c in reads), None)
        if raw:
            return Field(value=None, raw_text=raw, confidence="low", reasons=['אורך ת"ז לא תקין'])
        return _missing()

    counts = Counter(n for n, _ in valid)
    value, votes = counts.most_common(1)[0]
    source = next(c.source for n, c in valid if n == value)
    consistent = len(counts) == 1
    supporters = [c for n, c in valid if n == value]
    corroborated = len(supporters) >= 2 or any(c.highlighted for c in supporters)
    level, reasons = _id_confidence(id_checksum_ok(value), consistent, corroborated)
    if not consistent:
        reasons.insert(0, "קריאות לא עקביות: " + " / ".join(counts))
    # one unconfirmed handwritten read is never better than low
    if source == "handwritten" and votes < 2 and level != "high":
        level = "low"
        reasons.append(HANDWRITTEN)
    return Field(value=value, raw_text=candidates[0].value, confidence=level, source=source, reasons=reasons)


# ---- central / commitment numbers ---------------------------------------------------------------

def _build_numbers(items: list[RawValue], barcodes: set[str], rule: NumberRule, *,
                   prefer_marked: bool = False) -> list[Field]:
    """A barcode match proves a number is on the page, not that it is the wanted one. So when several
    candidates compete, the highlighted ones win and an unhighlighted barcode match is only medium."""
    if prefer_marked:
        items = _prefer_highlighted(items)
    distinct = {rule.clean(i.value) for i in items} - {""}
    competing = prefer_marked and len(distinct) > 1 and not all(i.highlighted for i in items)

    out: list[Field] = []
    seen: set[str] = set()
    for it in items:
        value = rule.clean(it.value)
        if not value or value in seen:
            continue
        seen.add(value)
        field = Field(value=value, raw_text=it.value, source=it.source, confidence="medium")
        if not rule.is_valid(value):
            field.confidence, field.reasons = "low", [rule.flag_reason]
        elif value in barcodes:
            field.source = "barcode"
            if competing:
                field.reasons = [AMBIGUOUS_NUMBER]
            else:
                field.confidence = "high"
        elif it.source == "handwritten":
            field.confidence, field.reasons = "low", [HANDWRITTEN]
        out.append(field)
    return out or [_missing()]


# ---- received date ------------------------------------------------------------------------------

def build_received_date(raw: RawExtraction) -> Field:
    stamp, hand, main = raw.stamp_date, raw.handwritten_date, raw.received_date
    d_stamp, d_hand, d_main = (normalize_date(x.value) for x in (stamp, hand, main))
    if d_stamp:
        chosen, source = d_stamp, "stamp"
    elif d_main:
        chosen, source = d_main, main.source
    else:
        chosen, source = d_hand, "handwritten"
    raw_text = stamp.value or main.value or hand.value
    if not chosen:
        if raw_text:
            return Field(value=None, raw_text=raw_text, confidence="low", reasons=["תאריך לא תקין"])
        return _missing()

    reasons: list[str] = []
    if d_stamp and d_hand and d_stamp != d_hand:
        level: Confidence = "low"
        reasons.append(f"חותמת {d_stamp:%d/%m/%Y} שונה מכתב יד {d_hand:%d/%m/%Y}")
    elif d_stamp and d_hand:
        level = "high"
    elif source == "handwritten":
        level = "low"
        reasons.append(HANDWRITTEN)
    else:
        level = "medium"
    if chosen > date.today():
        level = "low"
        reasons.append("תאריך בעתיד")
    elif chosen.year < 2000:
        level = "low"
        reasons.append("תאריך לא סביר")
    return Field(value=chosen.isoformat(), raw_text=raw_text, confidence=level, source=source, reasons=reasons)


# ---- sender -------------------------------------------------------------------------------------

def build_sender(rv: RawValue, others: list[RawValue] | None = None) -> Field:
    text = (rv.value or "").strip()
    if not text:
        return _missing()
    match = match_sender(text)
    if match is None:
        return Field(value=None, raw_text=text, confidence="low", source=rv.source,
                     reasons=[f"שולח לא ברשימה: {text}"])

    level: Confidence = "high" if match.exact else "medium"
    reasons = [] if match.exact else [f"התאמה מקורבת מתוך: {text}"]
    rivals = {o.value.strip() for o in others or [] if o.value and o.value.strip()}
    rivals = {r for r in rivals if (m := match_sender(r)) is None or m.name != match.name}
    if rivals and not rv.highlighted:   # several entities on the page and ours is not the marked one
        level = "medium"
        reasons.append("כמה גורמים בטופס: " + " / ".join(sorted(rivals)))
    return Field(value=match.name, raw_text=text, source=rv.source, confidence=level, reasons=reasons)


# ---- assembly -----------------------------------------------------------------------------------

def build_record(raw: RawExtraction, barcode_texts: list[str], *, low_quality: bool = False,
                 provider: str | None = None, page_number: int | None = None) -> CommitmentRecord:
    barcodes = {t.strip() for t in barcode_texts}
    central_values = {CENTRAL.clean(c.value) for c in raw.central_numbers} - {""}
    # a central number is never also a commitment number
    commitment_items = [c for c in raw.commitment_numbers if CENTRAL.clean(c.value) not in central_values]

    rec = CommitmentRecord(
        template=raw.template, provider=provider,
        page_numbers=[page_number] if page_number is not None else [],
        first_name=build_name(raw.first_name),
        last_name=build_name(raw.last_name),
        id_number=build_id(raw.id_numbers),
        central_numbers=_build_numbers(raw.central_numbers, barcodes, CENTRAL),
        received_date=build_received_date(raw),
        sender=build_sender(raw.sender, raw.other_senders),
        commitment_numbers=_build_numbers(commitment_items, barcodes, COMMITMENT, prefer_marked=True),
    )
    if low_quality or raw.image_unreadable:
        for f in rec.all_fields():
            f.confidence = "low"
            if LOW_QUALITY not in f.reasons:
                f.reasons.append(LOW_QUALITY)
    return rec
