"""Response models of the REST API."""
from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.db.models import Document


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
            done=all(p.status in ("ready", "error") for p in pages),
            pages=[PageStatus(id=p.id, page_number=p.page_number, status=p.status, error=p.error,
                              record_id=p.record_id) for p in pages])


class ApproveCleanResult(BaseModel):
    approved: list[uuid.UUID]
    skipped_duplicates: list[uuid.UUID]
