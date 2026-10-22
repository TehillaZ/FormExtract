"""Response models of the REST API."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.db.models import Document
from app.evaluation import EvaluationReport


class PageStatus(BaseModel):
    id: uuid.UUID
    page_number: int
    status: str            # pending | processing | ready | error
    error: str | None = None
    record_id: uuid.UUID | None = None


class DocumentStatus(BaseModel):
    id: uuid.UUID
    filename: str
    duplicate: bool = False       # identical file already uploaded: not processed again (ADR-010)
    done: bool
    pages: list[PageStatus]

    @classmethod
    def of(cls, doc: Document, duplicate: bool = False) -> DocumentStatus:
        pages = sorted(doc.pages, key=lambda p: p.page_number)
        return cls(
            id=doc.id, filename=doc.filename, duplicate=duplicate,
            done=bool(pages) and all(p.status in ("ready", "error") for p in pages),   # no pages yet is not "done"
            pages=[PageStatus(id=p.id, page_number=p.page_number, status=p.status, error=p.error,
                              record_id=p.record_id) for p in pages])


class ActivePage(BaseModel):
    """A page that has no record yet: waiting, being read, or failed. The form can already be viewed."""
    id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page_number: int
    status: str            # pending | processing | error
    error: str | None = None


class ApproveCleanResult(BaseModel):
    approved: list[uuid.UUID]
    skipped_duplicates: list[uuid.UUID]


class EvaluationOverview(BaseModel):
    """Saved accuracy reports plus how much of the verified data exists, so the screen can say what was NOT run."""
    reports: list[EvaluationReport]
    pages: int          # pages with a hand-verified answer
    dev_pages: int
    test_pages: int


class CorrectionExample(BaseModel):
    old: str | None
    new: str | None


class CorrectionGroup(BaseModel):
    """One kind of repeated mistake: the same field, on the same sender's form type."""
    field: str
    sender: str | None
    template: str | None
    count: int
    unflagged: int                # corrections of values the system had shown as certain
    sources: dict[str, int]       # how the wrong value appeared: handwritten, printed, ...
    examples: list[CorrectionExample]
    last_at: datetime
