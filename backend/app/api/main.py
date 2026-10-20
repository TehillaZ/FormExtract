"""REST API (PLAN 7). OpenAPI docs are served at /docs."""
from __future__ import annotations

import hashlib
import uuid
from datetime import date
from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import repo
from app.db.models import Document, Page
from app.db.session import get_session, init_db, is_initialized
from app.pipeline.ingest import file_to_images
from app.pipeline.process import process_document, process_page
from app.schemas import CommitmentRecord
from app.storage import get_storage
from app.validation.senders import all_senders

MAX_UPLOAD_BYTES = 50 * 1024 * 1024

app = FastAPI(title="FormExtract", description="Commitment-form extraction for the central virology lab")
app.state.providers = None   # tests inject fake vision providers here
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])

DB = Annotated[Session, Depends(get_session)]


@app.on_event("startup")
def _startup() -> None:
    if not is_initialized():   # tests initialise their own database first
        init_db()


# ---- schemas ------------------------------------------------------------------------------------

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


class ApproveCleanResult(BaseModel):
    approved: list[uuid.UUID]
    skipped_duplicates: list[uuid.UUID]


def _doc_status(doc: Document, duplicate: bool = False) -> DocumentStatus:
    pages = sorted(doc.pages, key=lambda p: p.page_number)
    return DocumentStatus(
        id=doc.id, filename=doc.filename, duplicate=duplicate,
        done=all(p.status in ("ready", "error") for p in pages),
        pages=[PageStatus(id=p.id, page_number=p.page_number, status=p.status, error=p.error, record_id=p.record_id)
               for p in pages])


# ---- documents ----------------------------------------------------------------------------------

@app.post("/documents", response_model=list[DocumentStatus], status_code=202)
async def upload(files: Annotated[list[UploadFile], File()], background: BackgroundTasks, db: DB):
    """Upload one or several files (PDF, JPG, PNG, HEIC). Returns at once; processing runs in the background."""
    out: list[DocumentStatus] = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{f.filename}: הקובץ גדול מדי")
        digest = hashlib.sha256(data).hexdigest()
        existing = db.scalars(sa.select(Document).where(Document.file_hash == digest)).first()
        if existing:
            out.append(_doc_status(existing, duplicate=True))
            continue
        try:
            images = file_to_images(f.filename or "", data)
        except Exception:
            raise HTTPException(400, f"{f.filename}: לא ניתן לקרוא את הקובץ") from None
        if not images:
            raise HTTPException(400, f"{f.filename}: הקובץ ריק")
        doc = Document(id=uuid.uuid4(), filename=f.filename or "upload", file_hash=digest)
        storage = get_storage()
        for n, img in enumerate(images, start=1):
            doc.pages.append(Page(page_number=n, status="pending",
                                  original_path=storage.save_image(f"{doc.id}/{n}_original.png", img)))
        db.add(doc)
        db.commit()
        background.add_task(process_document, doc.id, app.state.providers)
        out.append(_doc_status(doc))
    return out


@app.get("/documents/{document_id}", response_model=DocumentStatus)
def document_status(document_id: uuid.UUID, db: DB):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "המסמך לא נמצא")
    return _doc_status(doc)


@app.post("/pages/{page_id}/reprocess", response_model=PageStatus, status_code=202)
def reprocess(page_id: uuid.UUID, background: BackgroundTasks, db: DB):
    """Retry a page that failed (a crash or a rate limit)."""
    page = db.get(Page, page_id)
    if page is None:
        raise HTTPException(404, "העמוד לא נמצא")
    if page.status == "processing":
        raise HTTPException(409, "העמוד כבר בעיבוד")
    page.status, page.error = "pending", None
    db.commit()
    background.add_task(process_page, page_id, app.state.providers)
    return PageStatus(id=page.id, page_number=page.page_number, status=page.status)


@app.get("/pages/{page_id}/image")
def page_image(page_id: uuid.UUID, db: DB, original: bool = False):
    page = db.get(Page, page_id)
    path = page and (page.original_path if original or not page.image_path else page.image_path)
    if not path:
        raise HTTPException(404, "התמונה לא נמצאה")
    return FileResponse(get_storage().abspath(path), media_type="image/png")


# ---- records ------------------------------------------------------------------------------------

@app.get("/records", response_model=list[CommitmentRecord])
def list_records(
    db: DB,
    status: Annotated[str | None, Query(pattern="^(pending|approved)$")] = None,
    sender: str | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    q: str | None = None,
    needs_review: bool | None = None,
    document_id: Annotated[list[uuid.UUID] | None, Query()] = None,
    limit: Annotated[int, Query(le=1000)] = 200,
    offset: int = 0,
):
    return repo.list_records(db, status=status, sender=sender, date_from=date_from, date_to=date_to, q=q,
                             needs_review=needs_review, document_ids=document_id, limit=limit, offset=offset)


@app.post("/records/approve-clean", response_model=ApproveCleanResult)
def approve_clean(db: DB, document_id: Annotated[list[uuid.UUID] | None, Query()] = None):
    """'Approve all clean rows': every pending record with nothing flagged for review."""
    approved, skipped = repo.approve_clean(db, document_id)
    return ApproveCleanResult(approved=approved, skipped_duplicates=skipped)


@app.get("/records/{record_id}", response_model=CommitmentRecord)
def get_record(record_id: uuid.UUID, db: DB):
    try:
        return repo.get_record(db, record_id)
    except repo.NotFound:
        raise HTTPException(404, "הרשומה לא נמצאה") from None


@app.patch("/records/{record_id}", response_model=CommitmentRecord)
def patch_record(record_id: uuid.UUID, changes: dict[str, Any], db: DB):
    """Body: {"field": "new value"} or {"central_numbers": ["939376", ...]}. An empty value clears the field."""
    try:
        return repo.patch_record(db, record_id, changes)
    except repo.NotFound:
        raise HTTPException(404, "הרשומה לא נמצאה") from None
    except repo.InvalidValue as e:
        raise HTTPException(422, str(e)) from None


@app.post("/records/{record_id}/approve", response_model=CommitmentRecord)
def approve(record_id: uuid.UUID, db: DB):
    try:
        return repo.approve_record(db, record_id)
    except repo.NotFound:
        raise HTTPException(404, "הרשומה לא נמצאה") from None
    except repo.DuplicateCommitmentError as e:
        raise HTTPException(409, str(e)) from None


@app.get("/senders", response_model=list[str])
def senders():
    """The closed sender list, for the correction dropdown."""
    return all_senders()


@app.get("/health")
def health():
    return {"ok": True}
