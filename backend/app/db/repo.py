"""Persistence for records: save, read, search, correct, approve, duplicate warnings (ADR-010, ADR-016).

Input validation lives in app.validation.manual; this module only talks to the database.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.models import CorrectionRow, Record, RecordCentralNumber, RecordCommitmentNumber
from app.schemas import CommitmentRecord, Correction, Field, PastFix, Suggestion
from app.validation.manual import LIST_RULES, SCALAR_FIELDS, InvalidValue, clean_list, clean_scalar

__all__ = ["correction_summary", "NotFound", "DuplicateCommitmentError", "InvalidValue", "save_record", "get_record", "list_records",
           "patch_record", "approve_record", "approve_clean"]

MANUAL = "תוקן ידנית"
CONFIRMED = "אושר ידנית"
CONFIRMED_EMPTY = "אושר ידנית: אין בטופס"
_WITH_CHILDREN = (selectinload(Record.commitment_numbers), selectinload(Record.central_numbers),
                  selectinload(Record.corrections))


class NotFound(Exception):
    pass


class DuplicateCommitmentError(Exception):
    def __init__(self, numbers: list[str]):
        self.numbers = numbers
        super().__init__("מספר התחייבות כבר קיים ברשומה מאושרת: " + ", ".join(numbers))


# ---- row <-> record -----------------------------------------------------------------------------

def _values(fields: list[Field]) -> list[str]:
    return [f.value for f in fields if f.value]


def _sync_columns(row: Record, rec: CommitmentRecord) -> None:
    """Copy the record into the row: the JSON document plus the columns used for search and filtering."""
    row.data = rec.model_dump(mode="json", exclude={"corrections", "duplicate_warnings", "suggestions", "id", "status", "approved_at"})
    row.id_number = rec.id_number.value
    row.sender = rec.sender.value
    row.received_date = date.fromisoformat(rec.received_date.value) if rec.received_date.value else None
    row.needs_review = rec.needs_review()
    _sync_numbers(row, rec)


def _sync_numbers(row: Record, rec: CommitmentRecord) -> None:
    """Keep the searchable number rows in step with the record. Rows are replaced only when the numbers
    changed: replacing identical approved rows would briefly hold the same number twice and trip the
    unique index (ADR-016)."""
    central = list(dict.fromkeys(_values(rec.central_numbers)))
    if [n.value for n in row.central_numbers] != central:
        row.central_numbers = [RecordCentralNumber(value=v) for v in central]
    commitment = list(dict.fromkeys(_values(rec.commitment_numbers)))
    if [n.value for n in row.commitment_numbers] != commitment:
        row.commitment_numbers = [RecordCommitmentNumber(value=v, status=row.status) for v in commitment]
    else:
        for n in row.commitment_numbers:
            n.status = row.status   # the status mirror must follow the record (pending frees the number)


def _to_record(row: Record) -> CommitmentRecord:
    return CommitmentRecord.model_validate({
        **row.data, "id": row.id, "status": row.status, "approved_at": row.approved_at,
        "corrections": [Correction(field=c.field, old_value=c.old_value, new_value=c.new_value, at=c.at)
                        for c in row.corrections],
    })


def _row(s: Session, record_id: uuid.UUID) -> Record:
    row = s.scalars(sa.select(Record).where(Record.id == record_id).options(*_WITH_CHILDREN)).first()
    if row is None:
        raise NotFound(str(record_id))
    return row


def _present(s: Session, rows: list[Record]) -> list[CommitmentRecord]:
    warnings = _duplicate_warnings(s, rows)
    out = [_to_record(row) for row in rows]
    suggestions = _suggestions(s, out)
    for rec in out:
        rec.duplicate_warnings = warnings[rec.id]
        rec.suggestions = suggestions[rec.id]
    return out


# ---- duplicates ---------------------------------------------------------------------------------

def _duplicate_warnings(s: Session, rows: list[Record]) -> dict[uuid.UUID, list[str]]:
    """Warnings only (ADR-010): another record shares a central or commitment number. Two queries in total."""
    warnings: dict[uuid.UUID, list[str]] = {r.id: [] for r in rows}
    for model, attr, label in ((RecordCentralNumber, "central_numbers", "מספר מרכזי"),
                               (RecordCommitmentNumber, "commitment_numbers", "מספר התחייבות")):
        mine = {r.id: {n.value for n in getattr(r, attr)} for r in rows}
        wanted = set().union(*mine.values())
        if not wanted:
            continue
        owners: dict[str, set[uuid.UUID]] = defaultdict(set)
        for record_id, value in s.execute(sa.select(model.record_id, model.value).where(model.value.in_(wanted))):
            owners[value].add(record_id)
        for record_id, values in mine.items():
            warnings[record_id] += [f"{label} {v} כבר קיים ברשומה אחרת"
                                    for v in sorted(values) if owners[v] - {record_id}]
    return warnings


# ---- suggestions from earlier corrections -------------------------------------------------------
# "Smart memory": when people keep changing the same reading to the same value on one sender's forms, offer that
# change on the next form with the same reading. It is only an offer: nothing is applied without a person.

SUGGEST_MIN_FIXES = 3        # how many agreeing corrections it takes before anything is offered
SUGGEST_MIN_SHARE = 0.75     # and the share of all corrections of that reading that agree


def _current_readings(rec: CommitmentRecord) -> dict[str, str | None]:
    """The reading of every field a person has not already looked at, as it would be logged if corrected.
    An empty sender is a reading too (None), but only on a form of a known type: on forms of that type people
    keep filling the same sender in, and "empty" alone, on any form, would say nothing."""
    out: dict[str, str | None] = {}
    for name in SCALAR_FIELDS:
        f: Field = getattr(rec, name)
        if f.value and f.source != "manual":
            out[name] = f.value
    if rec.sender.value is None and rec.sender.source != "manual" and rec.template:
        out["sender"] = None
    for name in LIST_RULES:
        fields: list[Field] = getattr(rec, name)
        if fields and all(f.source != "manual" for f in fields) and _values(fields):
            out[name] = ", ".join(_values(fields))
    return out


def _suggestions(s: Session, recs: list[CommitmentRecord]) -> dict[uuid.UUID, list[Suggestion]]:
    out: dict[uuid.UUID, list[Suggestion]] = {r.id: [] for r in recs}
    readings = {r.id: _current_readings(r) for r in recs if r.status == "pending"}
    values = [v for rd in readings.values() for v in rd.values()]
    wanted = {v for v in values if v is not None}
    if not values:
        return out
    seen = CorrectionRow.old_value.in_(wanted)
    if None in values:   # someone had an empty sender: earlier fixes of an empty sender are needed too
        seen = sa.or_(seen, CorrectionRow.old_value.is_(None))
    past = list(s.scalars(sa.select(CorrectionRow).where(seen)
                          .order_by(CorrectionRow.at.desc(), CorrectionRow.id.desc())))
    for rec in recs:
        for name, current in readings.get(rec.id, {}).items():
            # same field, same reading, same sender (the sender field itself is judged by the reading alone)
            same = [c for c in past if c.field == name and c.old_value == current and c.record_id != rec.id
                    and (name == "sender" or c.sender == rec.sender.value)
                    and (not c.template or not rec.template or c.template == rec.template)
                    and (current is not None or c.template == rec.template)]   # an empty reading needs the same form type
            if not same:
                continue
            tally = defaultdict(int)
            for c in same:
                tally[c.new_value] += 1
            best, times = max(tally.items(), key=lambda kv: kv[1])
            if times < SUGGEST_MIN_FIXES or times / len(same) < SUGGEST_MIN_SHARE:
                continue
            out[rec.id].append(Suggestion(
                field=name, current=current, suggested=best, times=times, total=len(same), sender=rec.sender.value,
                examples=[PastFix(old=c.old_value, new=c.new_value, at=c.at) for c in same if c.new_value == best][:3]))
    return out


# ---- create / read ------------------------------------------------------------------------------

def save_record(s: Session, rec: CommitmentRecord) -> CommitmentRecord:
    row = Record(id=rec.id, document_id=rec.document_id, status=rec.status)
    _sync_columns(row, rec)
    s.add(row)
    s.commit()
    return get_record(s, rec.id)


def get_record(s: Session, record_id: uuid.UUID) -> CommitmentRecord:
    return _present(s, [_row(s, record_id)])[0]


def _filtered(stmt, *, status: str | None, sender: str | None, date_from: date | None, date_to: date | None,
              q: str | None, needs_review: bool | None, document_ids: list[uuid.UUID] | None):
    """Apply the record filters to a select. Shared by listing, counting and exporting, so they always agree."""
    # each condition is built only when its filter is given (comparing a column with None would raise)
    filters = [
        (status, lambda: Record.status == status),
        (sender, lambda: Record.sender == sender),
        (date_from, lambda: Record.received_date >= date_from),
        (date_to, lambda: Record.received_date <= date_to),
        (needs_review is not None, lambda: Record.needs_review == needs_review),
        (document_ids, lambda: Record.document_id.in_(document_ids)),
    ]
    for active, condition in filters:
        if active:
            stmt = stmt.where(condition())
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(sa.or_(
            Record.id_number.like(like),
            Record.data["first_name"]["value"].as_string().like(like),   # names live in the record's JSON
            Record.data["last_name"]["value"].as_string().like(like),
            Record.id.in_(sa.select(RecordCentralNumber.record_id).where(RecordCentralNumber.value.like(like))),
            Record.id.in_(sa.select(RecordCommitmentNumber.record_id).where(RecordCommitmentNumber.value.like(like))),
        ))
    return stmt


def list_records(s: Session, *, status: str | None = None, sender: str | None = None,
                 date_from: date | None = None, date_to: date | None = None, q: str | None = None,
                 needs_review: bool | None = None, document_ids: list[uuid.UUID] | None = None,
                 limit: int = 200, offset: int = 0) -> list[CommitmentRecord]:
    stmt = sa.select(Record).options(*_WITH_CHILDREN).order_by(Record.created_at.desc(), Record.id)
    stmt = _filtered(stmt, status=status, sender=sender, date_from=date_from, date_to=date_to, q=q,
                     needs_review=needs_review, document_ids=document_ids)
    return _present(s, list(s.scalars(stmt.limit(limit).offset(offset))))


def count_records(s: Session, *, status: str | None = None, sender: str | None = None,
                  date_from: date | None = None, date_to: date | None = None, q: str | None = None,
                  needs_review: bool | None = None, document_ids: list[uuid.UUID] | None = None) -> int:
    """How many records match, ignoring paging: the total behind a page of results."""
    stmt = _filtered(sa.select(sa.func.count()).select_from(Record), status=status, sender=sender,
                     date_from=date_from, date_to=date_to, q=q, needs_review=needs_review, document_ids=document_ids)
    return s.scalar(stmt) or 0


# ---- corrections --------------------------------------------------------------------------------

def _manual(value: str | None, raw: str | None = None) -> Field:
    """A value a person typed. Typing nothing means "this form has none": confirmed empty, not a missing field."""
    if value is None:
        return Field(value=None, raw_text=raw, confidence="high", source="manual", reasons=[CONFIRMED_EMPTY])
    return Field(value=value, raw_text=raw, confidence="high", source="manual", reasons=[MANUAL])


def _confirmed(value: str | None, raw: str | None = None) -> Field:
    """A value a person looked at and saved unchanged: it stops being flagged."""
    if value is None:
        return Field(value=None, raw_text=raw, confidence="high", source="manual", reasons=[CONFIRMED_EMPTY])
    return Field(value=value, raw_text=raw, confidence="high", source="manual", reasons=[CONFIRMED])


Logged = tuple[str, str | None, str | None, str | None, str | None]   # field, old, new, source, confidence before


def _weakest(fields: list[Field]) -> str | None:
    order = {"low": 0, "medium": 1, "high": 2}
    return min((f.confidence for f in fields), key=order.get, default=None)


def _apply_changes(rec: CommitmentRecord, changes: dict) -> tuple[list[Logged], bool]:
    """Validate and apply what a person saved to rec in place.

    Returns (log, touched). `log` holds (field, old, new, source and confidence before) for values that really changed. `touched` is also true
    when an unchanged but flagged field was saved: that is a confirmation, not a correction, so it is not logged.
    """
    unknown = set(changes) - set(SCALAR_FIELDS) - set(LIST_RULES)
    if unknown:
        raise InvalidValue("שדה לא מוכר: " + ", ".join(sorted(unknown)))
    log: list[Logged] = []
    touched = False
    for name, new in changes.items():
        if name in SCALAR_FIELDS:
            old: Field = getattr(rec, name)
            value = clean_scalar(name, new if isinstance(new, str) else None)
            if value != old.value:
                setattr(rec, name, _manual(value, raw=old.raw_text))
                log.append((name, old.value, value, old.source, old.confidence))
                touched = True
            elif old.confidence != "high":
                setattr(rec, name, _confirmed(value, raw=old.raw_text))
                touched = True
        else:
            old_fields: list[Field] = getattr(rec, name)
            old_values = _values(old_fields)
            values = clean_list(name, list(new or []))
            if values != old_values:
                setattr(rec, name, [_manual(v) for v in values] or [_manual(None)])
                log.append((name, ", ".join(old_values) or None, ", ".join(values) or None,
                            next((f.source for f in old_fields if f.value), None), _weakest(old_fields)))
                touched = True
            elif any(f.confidence != "high" for f in old_fields):
                setattr(rec, name, [_confirmed(v) for v in values] or [_confirmed(None)])
                touched = True
    return log, touched


def patch_record(s: Session, record_id: uuid.UUID, changes: dict) -> CommitmentRecord:
    """Apply what a person saved. A changed field is logged (old -> new) and becomes high-confidence/manual.
    A flagged field saved unchanged is confirmed (high, manual) without a log entry."""
    row = _row(s, record_id)
    rec = _to_record(row)
    log, touched = _apply_changes(rec, changes)
    if not touched:
        return get_record(s, record_id)
    if log and row.status == "approved":   # a real edit sends the record back for approval; a confirmation does not
        row.status, row.approved_at = "pending", None
    now = datetime.now(UTC)
    sender = rec.sender.value or rec.sender.raw_text   # the sender after the fix: where the mistake belongs
    row.corrections.extend(CorrectionRow(field=f, old_value=o, new_value=n, at=now, sender=sender,
                                         template=rec.template, source=src, confidence=conf)
                           for f, o, n, src, conf in log)
    _sync_columns(row, rec)
    s.commit()
    return get_record(s, record_id)


# ---- approval -----------------------------------------------------------------------------------

def approve_record(s: Session, record_id: uuid.UUID) -> CommitmentRecord:
    row = _row(s, record_id)
    row.status, row.approved_at = "approved", datetime.now(UTC)
    for n in row.commitment_numbers:
        n.status = "approved"
    try:
        s.commit()
    except IntegrityError:   # the partial unique index (ADR-016) rejected a number that is already approved
        s.rollback()
        mine = [n.value for n in _row(s, record_id).commitment_numbers]
        taken = s.scalars(sa.select(RecordCommitmentNumber.value).where(
            RecordCommitmentNumber.value.in_(mine), RecordCommitmentNumber.status == "approved")).all()
        raise DuplicateCommitmentError(sorted(set(taken))) from None
    return get_record(s, record_id)


def approve_clean(s: Session, document_ids: list[uuid.UUID] | None = None) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    """Approve every pending record with nothing to review. Returns (approved, skipped because of a duplicate)."""
    approved, skipped = [], []
    for rec in list_records(s, status="pending", needs_review=False, document_ids=document_ids, limit=10_000):
        try:
            approve_record(s, rec.id)
            approved.append(rec.id)
        except DuplicateCommitmentError:
            skipped.append(rec.id)
    return approved, skipped


# ---- recurring mistakes -------------------------------------------------------------------------

def correction_summary(s: Session, *, examples: int = 3, min_count: int = 1) -> list[dict]:
    """Corrections grouped by field, sender and form type, most frequent first. Each group keeps a few
    old -> new examples and how many of the mistakes the system had NOT flagged (confidence high): those
    are the ones that would have reached the database unnoticed."""
    rows = s.execute(sa.select(CorrectionRow).order_by(CorrectionRow.at.desc(), CorrectionRow.id.desc())).scalars()
    groups: dict[tuple, dict] = {}
    for c in rows:
        key = (c.field, c.sender, c.template)
        g = groups.setdefault(key, {"field": c.field, "sender": c.sender, "template": c.template, "count": 0,
                                    "unflagged": 0, "sources": defaultdict(int), "examples": [], "last_at": c.at})
        g["count"] += 1
        g["unflagged"] += c.confidence == "high"
        if c.source:
            g["sources"][c.source] += 1
        pair = (c.old_value, c.new_value)
        if len(g["examples"]) < examples and pair not in [(e["old"], e["new"]) for e in g["examples"]]:
            g["examples"].append({"old": c.old_value, "new": c.new_value})
    out = [{**g, "sources": dict(g["sources"])} for g in groups.values() if g["count"] >= min_count]
    return sorted(out, key=lambda g: (-g["count"], -g["unflagged"], g["field"]))
