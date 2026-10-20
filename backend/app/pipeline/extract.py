"""Model output -> normalized fields with confidence (PLAN 5.2, 5.3)."""
from __future__ import annotations

import re
from collections import Counter
from datetime import date

from app.config import settings
from app.schemas import CommitmentRecord, Field, RawExtraction, RawValue
from app.validation.israeli_id import id_checksum_ok, normalize_id
from app.validation.senders import match_sender

NOT_FOUND = "לא נמצא"
HANDWRITTEN = "כתב יד"
LOW_QUALITY = "איכות תמונה נמוכה"


def _missing(reason: str = NOT_FOUND) -> Field:
    return Field(value=None, confidence="low", reasons=[reason])


# ---- dates --------------------------------------------------------------------------------------

_DATE_RE = re.compile(r"(\d{1,2})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{2,4})")


def normalize_date(raw: str | None) -> date | None:
    """dd/mm/yyyy (or yy) -> date. Israeli forms are day-first."""
    if not raw:
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


# ---- per-field builders -------------------------------------------------------------------------

def build_name(rv: RawValue) -> Field:
    v = (rv.value or "").strip()
    if not v:
        return _missing()
    # handwritten names cannot be verified -> flagged for a human look; printed ones are plausible
    if rv.source == "handwritten":
        return Field(value=v, raw_text=rv.value, source=rv.source, confidence="low", reasons=[HANDWRITTEN])
    return Field(value=v, raw_text=rv.value, source=rv.source, confidence="medium")


def build_id(candidates: list[RawValue]) -> Field:
    if any(c.highlighted for c in candidates):
        candidates = [c for c in candidates if c.highlighted]
    reads = [(normalize_id(c.value), c) for c in candidates if c.value]
    valid = [(n, c) for n, c in reads if n]
    if not valid:
        raw = next((c.value for _, c in reads), None)
        if raw:
            return Field(value=None, raw_text=raw, confidence="low", reasons=['אורך ת"ז לא תקין'])
        return _missing()
    counts = Counter(n for n, _ in valid)
    value, votes = counts.most_common(1)[0]
    src = next(c.source for n, c in valid if n == value)
    reasons: list[str] = []
    consistent = len(counts) == 1
    if not consistent:
        reasons.append("קריאות לא עקביות: " + " / ".join(counts))
    ok = id_checksum_ok(value)
    strict = settings.id_checksum_mode == "strict"

    if strict and not ok:
        level = "low"
        reasons.append("ספרת ביקורת לא תקינה")
    elif strict and ok and consistent:
        level = "high"
    elif not strict and not ok:
        level = "medium" if consistent else "low"
        reasons.append("ספרת ביקורת לא תקינה (מידע בלבד)")
    else:
        level = "medium" if consistent else "low"

    # an unverified single handwritten read is never better than low
    if src == "handwritten" and votes < 2 and level != "high":
        level = "low"
        reasons.append(HANDWRITTEN)
    return Field(value=value, raw_text=candidates[0].value, confidence=level, source=src, reasons=reasons)


def _build_number_list(items: list[RawValue], barcode_texts: set[str], *, valid, bad_reason,
                       prefer_highlighted: bool = False) -> list[Field]:
    """A barcode match proves the number is on the page, not that it is the wanted one. So when several
    candidates compete, the highlighted ones win, and an unhighlighted match is only medium."""
    if prefer_highlighted and any(i.highlighted for i in items):
        items = [i for i in items if i.highlighted]
    distinct = {valid.clean(i.value) for i in items if valid.clean(i.value)}
    competing = prefer_highlighted and len(distinct) > 1 and not all(i.highlighted for i in items)
    out: list[Field] = []
    seen: set[str] = set()
    for it in items:
        v = valid.clean(it.value)
        if not v or v in seen:
            continue
        seen.add(v)
        if not valid.ok(v):
            out.append(Field(value=v, raw_text=it.value, source=it.source, confidence="low", reasons=[bad_reason]))
        elif v in barcode_texts and competing:
            out.append(Field(value=v, raw_text=it.value, source="barcode", confidence="medium",
                             reasons=["כמה מספרים אפשריים בטופס"]))
        elif v in barcode_texts:
            out.append(Field(value=v, raw_text=it.value, source="barcode", confidence="high"))
        elif it.source == "handwritten":
            out.append(Field(value=v, raw_text=it.value, source=it.source, confidence="low", reasons=[HANDWRITTEN]))
        else:
            out.append(Field(value=v, raw_text=it.value, source=it.source, confidence="medium"))
    return out or [_missing()]


class _Central:
    clean = staticmethod(lambda s: re.sub(r"\D", "", s or ""))
    ok = staticmethod(lambda v: len(v) == 6)


class _Commitment:
    clean = staticmethod(lambda s: re.sub(r"\s+", "", s or ""))
    ok = staticmethod(lambda v: 4 <= len(v) <= 12 and re.fullmatch(r"[A-Za-z]?\d+", v) is not None)


def build_central_numbers(items: list[RawValue], barcode_texts: set[str]) -> list[Field]:
    return _build_number_list(items, barcode_texts, valid=_Central, bad_reason="מספר מרכזי אינו בן 6 ספרות")


def build_commitment_numbers(items: list[RawValue], barcode_texts: set[str]) -> list[Field]:
    return _build_number_list(items, barcode_texts, valid=_Commitment, bad_reason="פורמט מספר התחייבות חריג",
                              prefer_highlighted=True)


def build_received_date(raw: RawExtraction) -> Field:
    stamp, hand, main = raw.stamp_date, raw.handwritten_date, raw.received_date
    d_stamp, d_hand, d_main = (normalize_date(x.value) for x in (stamp, hand, main))
    if d_stamp:
        chosen, src = d_stamp, "stamp"
    elif d_main:
        chosen, src = d_main, main.source
    else:
        chosen, src = d_hand, "handwritten"
    raw_text = stamp.value or main.value or hand.value
    if not chosen:
        if raw_text:
            return Field(value=None, raw_text=raw_text, confidence="low", reasons=["תאריך לא תקין"])
        return _missing()
    reasons: list[str] = []
    if d_stamp and d_hand and d_stamp != d_hand:
        level = "low"
        reasons.append(f"חותמת {d_stamp:%d/%m/%Y} שונה מכתב יד {d_hand:%d/%m/%Y}")
    elif d_stamp and d_hand:
        level = "high"
    elif src == "handwritten":
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
    return Field(value=chosen.isoformat(), raw_text=raw_text, confidence=level, source=src, reasons=reasons)


def build_sender(rv: RawValue, others: list[RawValue] | None = None) -> Field:
    text = (rv.value or "").strip()
    if not text:
        return _missing()
    m = match_sender(text)
    if m is None:
        return Field(value=None, raw_text=text, confidence="low", source=rv.source,
                     reasons=[f"שולח לא ברשימה: {text}"])
    level, reasons = ("high", []) if m.exact else ("medium", [f"התאמה מקורבת מתוך: {text}"])
    rivals = {o.value.strip() for o in others or [] if o.value and o.value.strip()}
    rivals = {r for r in rivals if (mo := match_sender(r)) is None or mo.name != m.name}
    if rivals and not rv.highlighted:
        level = "medium"
        reasons.append("כמה גורמים בטופס: " + " / ".join(sorted(rivals)))
    return Field(value=m.name, raw_text=text, source=rv.source, confidence=level, reasons=reasons)


# ---- assembly -----------------------------------------------------------------------------------

def all_fields(rec: CommitmentRecord) -> list[Field]:
    return [rec.first_name, rec.last_name, rec.id_number, rec.received_date, rec.sender,
            *rec.central_numbers, *rec.commitment_numbers]


def build_record(raw: RawExtraction, barcode_texts: list[str], *, low_quality: bool = False,
                 provider: str | None = None, page_number: int | None = None) -> CommitmentRecord:
    bc = {t.strip() for t in barcode_texts}
    centrals = {_Central.clean(c.value) for c in raw.central_numbers if c.value}
    rec = CommitmentRecord(
        template=raw.template, provider=provider,
        page_numbers=[page_number] if page_number is not None else [],
        first_name=build_name(raw.first_name),
        last_name=build_name(raw.last_name),
        id_number=build_id(raw.id_numbers),
        central_numbers=build_central_numbers(raw.central_numbers, bc),
        received_date=build_received_date(raw),
        sender=build_sender(raw.sender, raw.other_senders),
        commitment_numbers=build_commitment_numbers(
            [c for c in raw.commitment_numbers if _Central.clean(c.value) not in centrals], bc),
    )
    if low_quality or raw.image_unreadable:
        for f in all_fields(rec):
            f.confidence = "low"
            if LOW_QUALITY not in f.reasons:
                f.reasons.append(LOW_QUALITY)
    return rec


def needs_review(f: Field) -> bool:
    return f.confidence != "high"
