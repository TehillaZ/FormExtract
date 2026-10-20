"""REST API (PLAN 7). OpenAPI docs are served at /docs."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Any

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.schemas import ApproveCleanResult, DocumentStatus, PageStatus
from app.db import repo
from app.db.models import Document, Page
from app.db.session import get_session, init_db, is_initialized
from app.pipeline.process import process_document, process_page
from app.schemas import CommitmentRecord
from app.services.documents import UploadRejected, register_upload
from app.storage import get_storage
from app.validation.senders import all_senders


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not is_initialized():   # tests initialise their own database first
        init_db()
    yield


app = FastAPI(title="FormExtract", description="Commitment-form extraction for the central virology laboratory",
              lifespan=lifespan)
app.state.providers = None   # tests inject fake vision providers here
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])

DB = Annotated[Session, Depends(get_session)]


# ---- documents ----------------------------------------------------------------------------------

@app.post("/documents", response_model=list[DocumentStatus], status_code=202)
async def upload(files: Annotated[list[UploadFile], File()], background: BackgroundTasks, db: DB):
    """Upload one or several files (PDF, JPG, PNG, HEIC). Returns at once; processing runs in the background."""
    storage, out = get_storage(), []
    for f in files:
        try:
            doc, duplicate = register_upload(db, storage, f.filename or "", await f.read())
        except UploadRejected as e:
            raise HTTPException(e.status, e.message) from None
        if not duplicate:
            background.add_task(process_document, doc.id, app.state.providers)
        out.append(DocumentStatus.of(doc, duplicate))
    return out


@app.get("/documents/{document_id}", response_model=DocumentStatus)
def document_status(document_id: uuid.UUID, db: DB):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "המסמך לא נמצא")
    return DocumentStatus.of(doc)


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
