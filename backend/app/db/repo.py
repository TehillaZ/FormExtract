"""Persistence for records: save, read, search, correct, approve, duplicate warnings (ADR-010, ADR-016)."""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timezone

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import CorrectionRow, Record, RecordCentralNumber, RecordCommitmentNumber
from app.pipeline.extract import NOT_FOUND, all_fields, normalize_date
from app.schemas import CommitmentRecord, Correction, Field
from app.validation.israeli_id import normalize_id
from app.validation.senders import match_sender

SCALAR_FIELDS = ("first_name", "last_name", "id_number", "received_date", "sender")
LIST_FIELDS = ("central_numbers", "commitment_numbers")
MANUAL = "תוקן ידנית"


class NotFound(Exception):
    pass


class DuplicateCommitmentError(Exception):
    def __init__(self, numbers: list[str]):
        self.numbers = numbers
        super().__init__("מספר התחייבות כבר קיים ברשומה מאושרת: " + ", ".join(numbers))


class InvalidValue(ValueError):
    pass


def _values(fields: list[Field]) -> list[str]:
    return [f.value for f in fields if f.value]


def _sync_columns(row: Record, rec: CommitmentRecord) -> None:
    row.data = rec.model_dump(mode="json", exclude={"corrections", "duplicate_warnings", "id", "status"})
    row.id_number = rec.id_number.value
    row.sender = rec.sender.value
    row.received_date = date.fromisoformat(rec.received_date.value) if rec.received_date.value else None
    row.needs_review = any(f.confidence != "high" for f in all_fields(rec))
    row.central_numbers = [RecordCentralNumber(value=v) for v in dict.fromkeys(_values(rec.central_numbers))]
    row.commitment_numbers = [RecordCommitmentNumber(value=v, status=row.status)
                              for v in dict.fromkeys(_values(rec.commitment_numbers))]


def _to_record(row: Record) -> CommitmentRecord:
    return CommitmentRecord.model_validate({
        **row.data, "id": row.id, "status": row.status,
        "corrections": [Correction(field=c.field, old_value=c.old_value, new_value=c.new_value, at=c.at)
                        for c in row.corrections],
    })


def _row(s: Session, record_id: uuid.UUID) -> Record:
    row = s.get(Record, record_id)
    if row is None:
        raise NotFound(str(record_id))
    return row


def save_record(s: Session, rec: CommitmentRecord) -> CommitmentRecord:
    row = Record(id=rec.id, document_id=rec.document_id, status=rec.status)
    _sync_columns(row, rec)
    s.add(row)
    s.commit()
    return get_record(s, rec.id)


def get_record(s: Session, record_id: uuid.UUID) -> CommitmentRecord:
    row = _row(s, record_id)
    rec = _to_record(row)
    rec.duplicate_warnings = find_duplicates(s, row)
    return rec


def find_duplicates(s: Session, row: Record) -> list[str]:
    """Warnings only (ADR-010): another record shares a central or commitment number."""
    out: list[str] = []
    for model, label, mine in (
        (RecordCentralNumber, "מספר מרכזי", [n.value for n in row.central_numbers]),
        (RecordCommitmentNumber, "מספר התחייבות", [n.value for n in row.commitment_numbers]),
    ):
        if not mine:
            continue
        others = s.execute(sa.select(model.value).where(model.value.in_(mine), model.record_id != row.id)).scalars()
        out += [f"{label} {v} כבר קיים ברשומה אחרת" for v in sorted(set(others))]
    return out


def list_records(s: Session, *, status: str | None = None, sender: str | None = None,
                 date_from: date | None = None, date_to: date | None = None, q: str | None = None,
                 needs_review: bool | None = None, document_ids: list[uuid.UUID] | None = None,
                 limit: int = 200, offset: int = 0) -> list[CommitmentRecord]:
    stmt = sa.select(Record).order_by(Record.created_at.desc(), Record.id)
    if status:
        stmt = stmt.where(Record.status == status)
    if sender:
        stmt = stmt.where(Record.sender == sender)
    if date_from:
        stmt = stmt.where(Record.received_date >= date_from)
    if date_to:
        stmt = stmt.where(Record.received_date <= date_to)
    if needs_review is not None:
        stmt = stmt.where(Record.needs_review == needs_review)
    if document_ids:
        stmt = stmt.where(Record.document_id.in_(document_ids))
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(sa.or_(
            Record.id_number.like(like),
            Record.id.in_(sa.select(RecordCentralNumber.record_id).where(RecordCentralNumber.value.like(like))),
            Record.id.in_(sa.select(RecordCommitmentNumber.record_id).where(RecordCommitmentNumber.value.like(like))),
        ))
    out = []
    for r in s.execute(stmt.limit(limit).offset(offset)).scalars().all():
        rec = _to_record(r)
        rec.duplicate_warnings = find_duplicates(s, r)
        out.append(rec)
    return out


# ---- corrections --------------------------------------------------------------------------------

def _manual(value: str | None, raw: str | None = None) -> Field:
    if value is None:
        return Field(value=None, confidence="low", reasons=[NOT_FOUND])
    return Field(value=value, raw_text=raw, confidence="high", source="manual", reasons=[MANUAL])


def _clean_scalar(name: str, new: str | None) -> str | None:
    new = (new or "").strip()
    if not new:
        return None
    if name == "id_number":
        v = normalize_id(new)
        if v is None:
            raise InvalidValue('ת"ז חייבת להכיל בין 5 ל-9 ספרות')
        return v
    if name == "received_date":
        d = date.fromisoformat(new) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", new) else normalize_date(new)
        if d is None:
            raise InvalidValue("תאריך לא תקין")
        if d > date.today():
            raise InvalidValue("תאריך בעתיד")
        return d.isoformat()
    if name == "sender":
        m = match_sender(new)
        if m is None:
            raise InvalidValue("הגורם השולח אינו ברשימה")
        return m.name
    return new


def _clean_list(name: str, new: list[str | None]) -> list[str]:
    out: list[str] = []
    for v in new:
        v = (v or "").strip()
        if not v:
            continue
        if name == "central_numbers":
            v = re.sub(r"\D", "", v)
            if len(v) != 6:
                raise InvalidValue("מספר מרכזי חייב להכיל 6 ספרות")
        else:
            v = re.sub(r"\s+", "", v)
            if not 4 <= len(v) <= 12 or not re.fullmatch(r"[A-Za-z]?\d+", v):
                raise InvalidValue("מספר התחייבות: 4 עד 12 תווים, אות אופציונלית ואז ספרות")
        if v not in out:
            out.append(v)
    return out


def patch_record(s: Session, record_id: uuid.UUID, changes: dict[str, str | list[str | None] | None]) -> CommitmentRecord:
    """Apply human corrections. Each changed field is logged (old -> new) and becomes high-confidence/manual."""
    row = _row(s, record_id)
    rec = _to_record(row)
    unknown = set(changes) - set(SCALAR_FIELDS) - set(LIST_FIELDS)
    if unknown:
        raise InvalidValue("שדה לא מוכר: " + ", ".join(sorted(unknown)))
    log: list[tuple[str, str | None, str | None]] = []
    for name, new in changes.items():
        if name in SCALAR_FIELDS:
            old_field: Field = getattr(rec, name)
            value = _clean_scalar(name, new if isinstance(new, str) else None)
            if value == old_field.value:
                continue
            setattr(rec, name, _manual(value, raw=old_field.raw_text))
            log.append((name, old_field.value, value))
        else:
            old_vals = _values(getattr(rec, name))
            vals = _clean_list(name, list(new or []))
            if vals == old_vals:
                continue
            setattr(rec, name, [_manual(v) for v in vals] or [_manual(None)])
            log.append((name, ", ".join(old_vals) or None, ", ".join(vals) or None))
    if not log:
        return get_record(s, record_id)
    if row.status == "approved":   # editing an approved record sends it back for approval
        row.status = "pending"
        row.approved_at = None
    for name, old, new in log:
        row.corrections.append(CorrectionRow(field=name, old_value=old, new_value=new, at=datetime.now(timezone.utc)))
    row.commitment_numbers.clear()
    row.central_numbers.clear()
    s.flush()
    _sync_columns(row, rec)
    s.commit()
    return get_record(s, record_id)


def approve_record(s: Session, record_id: uuid.UUID) -> CommitmentRecord:
    row = _row(s, record_id)
    row.status = "approved"
    row.approved_at = datetime.now(timezone.utc)
    for n in row.commitment_numbers:
        n.status = "approved"
    try:
        s.commit()
    except IntegrityError:
        s.rollback()
        mine = [n.value for n in _row(s, record_id).commitment_numbers]
        taken = s.execute(
            sa.select(RecordCommitmentNumber.value)
            .where(RecordCommitmentNumber.value.in_(mine), RecordCommitmentNumber.status == "approved")
        ).scalars().all()
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
