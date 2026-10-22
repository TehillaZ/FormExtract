"""REST API (PLAN 7). OpenAPI docs are served at /docs."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.schemas import ApproveCleanResult, CorrectionGroup, DocumentStatus, EvaluationOverview, PageStatus
from app.db import repo
from app.db.models import Document, Page
from app.db.session import get_session, init_db, is_initialized
from app.evaluation import EvaluationStore
from app.pipeline.process import process_document, process_page
from app.schemas import CommitmentRecord
from app.services.documents import UploadRejected, register_upload
from app.services.export import to_csv, to_xlsx
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
                   allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Total-Count", "Content-Disposition"])

DB = Annotated[Session, Depends(get_session)]


def get_evaluation_store() -> EvaluationStore:
    return EvaluationStore()   # tests and the browser-test server override this dependency


class RecordFilters:
    """The filters of the records list, the export and the "approve clean" action: one definition."""

    def __init__(
        self,
        status: Annotated[str | None, Query(pattern="^(pending|approved)$")] = None,
        sender: str | None = None,
        date_from: Annotated[date | None, Query(alias="from")] = None,
        date_to: Annotated[date | None, Query(alias="to")] = None,
        q: str | None = None,
        needs_review: bool | None = None,
        document_id: Annotated[list[uuid.UUID] | None, Query()] = None,
    ):
        self.status, self.sender, self.date_from, self.date_to = status, sender, date_from, date_to
        self.q, self.needs_review, self.document_ids = q, needs_review, document_id

    def as_kwargs(self) -> dict:
        return {"status": self.status, "sender": self.sender, "date_from": self.date_from, "date_to": self.date_to,
                "q": self.q, "needs_review": self.needs_review, "document_ids": self.document_ids}


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
    """Retry a page that failed (a crash or a rate limit). A page that already produced a record is refused:
    its saved model answer must stay what the record's corrections were made against."""
    page = db.get(Page, page_id)
    if page is None:
        raise HTTPException(404, "העמוד לא נמצא")
    if page.record_id is not None:
        raise HTTPException(409, "העמוד כבר עובד ויש לו רשומה, לא ניתן לעבד אותו מחדש")
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
    response: Response,
    filters: Annotated[RecordFilters, Depends()],
    limit: Annotated[int, Query(le=1000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """One page of the matching records. The header X-Total-Count says how many match in all."""
    response.headers["X-Total-Count"] = str(repo.count_records(db, **filters.as_kwargs()))
    return repo.list_records(db, **filters.as_kwargs(), limit=limit, offset=offset)


EXPORTS = {
    "csv": (to_csv, "text/csv; charset=utf-8"),
    "xlsx": (to_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
}


@app.get("/export")
def export_records(db: DB, filters: Annotated[RecordFilters, Depends()], format: Literal["csv", "xlsx"] = "xlsx"):
    """The records matching the filters as an Excel file (for people) or CSV (for programs). Same filters as /records."""
    build, media_type = EXPORTS[format]
    records = repo.list_records(db, **filters.as_kwargs(), limit=100_000)
    filename = f"forms-{datetime.now():%Y%m%d-%H%M}.{format}"
    return Response(build(records), media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/evaluation", response_model=EvaluationOverview)
def evaluation(store: Annotated[EvaluationStore, Depends(get_evaluation_store)]):
    """Saved accuracy reports (written by scripts/evaluate.py) and how much verified data exists."""
    coverage = store.coverage()
    return EvaluationOverview(reports=store.reports(), pages=coverage.pages, dev_pages=coverage.dev, test_pages=coverage.test)


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


@app.get("/corrections/summary", response_model=list[CorrectionGroup])
def corrections_summary(db: DB, min_count: Annotated[int, Query(ge=1)] = 1):
    """Repeated mistakes: what people had to fix, grouped by field, sender and form type."""
    return repo.correction_summary(db, min_count=min_count)


@app.get("/senders", response_model=list[str])
def senders():
    """The closed sender list, for the correction dropdown."""
    return all_senders()


@app.get("/health")
def health():
    return {"ok": True}
