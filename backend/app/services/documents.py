"""Registering an upload: duplicate detection by file hash, page rendering, storing the original images."""
from __future__ import annotations

import hashlib
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models import Document, Page
from app.pipeline.ingest import file_to_images
from app.storage import Storage

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class UploadRejected(Exception):
    """The file cannot be accepted; `status` is the HTTP status the API should answer with."""

    def __init__(self, status: int, message: str):
        self.status, self.message = status, message
        super().__init__(message)


def register_upload(db: Session, storage: Storage, filename: str, data: bytes) -> tuple[Document, bool]:
    """Store a new document and its pages (status "pending"). Returns (document, is_duplicate).
    An identical file that was uploaded before is returned as is and not stored again (ADR-010)."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadRejected(413, f"{filename}: הקובץ גדול מדי")
    digest = hashlib.sha256(data).hexdigest()
    existing = db.scalars(sa.select(Document).where(Document.file_hash == digest)).first()
    if existing:
        return existing, True
    try:
        images = file_to_images(filename, data)
    except Exception:
        raise UploadRejected(400, f"{filename}: לא ניתן לקרוא את הקובץ") from None
    if not images:
        raise UploadRejected(400, f"{filename}: הקובץ ריק")

    doc = Document(id=uuid.uuid4(), filename=filename or "upload", file_hash=digest)
    for number, img in enumerate(images, start=1):
        doc.pages.append(Page(page_number=number, status="pending",
                              original_path=storage.save_image(f"{doc.id}/{number}_original.png", img)))
    db.add(doc)
    db.commit()
    return doc, False
