"""Background processing: page image -> enhanced image -> barcodes -> model -> record in the DB (ADR-005).

Each page goes through three small steps: claim it, run the pipeline, then store the result or the failure.
A failure on one page never stops the others.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.config import settings
from app.db import repo
from app.db.models import Document, Page
from app.db.session import session_scope
from app.pipeline.barcodes import decode_barcodes
from app.pipeline.extract import build_record
from app.pipeline.orientation import correct_quarter_turn, flip_180
from app.pipeline.preprocess import preprocess
from app.schemas import RawExtraction
from app.storage import get_storage
from app.vision import RateLimited, VisionProvider, get_provider

log = logging.getLogger(__name__)   # never log field values (PLAN 11)

PHOTO_EXTS = {".jpg", ".jpeg", ".heic", ".heif"}   # phone photos get the perspective fix

Providers = tuple[VisionProvider, VisionProvider | None]   # (primary, fallback)


def default_providers() -> Providers:
    primary = get_provider(settings.vision_provider)
    name = settings.vision_fallback_provider
    usable = name != settings.vision_provider and settings.has_api_key(name)
    return primary, (get_provider(name) if usable else None)


async def extract_with_fallback(img, primary: VisionProvider, fallback: VisionProvider | None) -> tuple[RawExtraction, str]:
    """The fallback provider sees a page only when the primary kept answering 429 (PLAN 11, ADR-003)."""
    try:
        return await primary.extract(img), primary.name
    except RateLimited:
        if fallback is None:
            raise
        return await fallback.extract(img), fallback.name


async def extract_oriented(img: np.ndarray, primary: VisionProvider, fallback: VisionProvider | None,
                           on_flip: Callable[[np.ndarray], None] | None = None
                           ) -> tuple[RawExtraction, str, np.ndarray]:
    """Extract once. If the model says the text is upside down, flip the page and extract once more (ADR-009).
    If the flipped page is also called upside down, the flag is unreliable here: keep the first answer.
    `on_flip` gets the turned page before the second call, so the reviewer sees it upright without waiting for it."""
    raw, name = await extract_with_fallback(img, primary, fallback)
    if not raw.text_upside_down:
        return raw, name, img
    flipped = flip_180(img)
    if on_flip:
        on_flip(flipped)
    raw_flipped, name_flipped = await extract_with_fallback(flipped, primary, fallback)
    if raw_flipped.text_upside_down:
        if on_flip:
            on_flip(img)   # the flag was unreliable: show the original again
        return raw, name, img
    return raw_flipped, name_flipped, flipped


@dataclass(frozen=True)
class _PageJob:
    page_id: uuid.UUID
    document_id: uuid.UUID
    number: int
    original_path: str
    is_photo: bool


def _claim(page_id: uuid.UUID) -> _PageJob | None:
    """Take a page for processing. A page that already has a record is never processed again: its saved model
    answer is what that record's corrections were made against, and a second run would replace it."""
    with session_scope() as s:
        page = s.get(Page, page_id)
        if page is None or page.record_id is not None:
            return None
        page.status, page.error = "processing", None
        s.commit()
        return _PageJob(page_id, page.document_id, page.page_number, page.original_path,
                        is_photo=Path(page.document.filename).suffix.lower() in PHOTO_EXTS)


def _show_image(page_id: uuid.UUID, image_path: str) -> None:
    """Make the page viewable now, before the slow model call: the reviewer sees the form while fields are read."""
    with session_scope() as s:
        page = s.get(Page, page_id)
        if page is not None:
            page.image_path = image_path
            s.commit()


def _store_success(job: _PageJob, rec, raw: RawExtraction, enhanced_path: str, barcodes: list[str]) -> None:
    rec.document_id, rec.page_ids = job.document_id, [job.page_id]
    with session_scope() as s:
        saved = repo.save_record(s, rec)
        page = s.get(Page, job.page_id)
        page.record_id, page.image_path, page.status = saved.id, enhanced_path, "ready"
        page.raw_extraction, page.barcodes = raw.model_dump(mode="json"), barcodes
        s.commit()


def _store_failure(page_id: uuid.UUID, exc: Exception) -> None:
    log.warning("page %s failed: %s", page_id, type(exc).__name__)
    with session_scope() as s:
        page = s.get(Page, page_id)
        page.status, page.error = "error", type(exc).__name__   # the type only: messages may carry field data
        s.commit()


async def process_page(page_id: uuid.UUID, providers: Providers | None = None) -> None:
    job = _claim(page_id)
    if job is None:
        return
    storage = get_storage()
    try:
        primary, fallback = providers or default_providers()
        original = storage.read_image(job.original_path)
        upright, _ = correct_quarter_turn(original)   # sideways scans are common; upside down is left to the model
        pre = preprocess(upright, is_photo=job.is_photo)
        enhanced_name = f"{job.document_id}/{job.number}_enhanced.png"
        _show_image(page_id, storage.save_image(enhanced_name, pre.image))
        raw, provider_name, final = await extract_oriented(
            pre.image, primary, fallback, on_flip=lambda turned: storage.save_image(enhanced_name, turned))
        enhanced = storage.save_image(enhanced_name, final)   # what the reviewer sees
        barcodes = sorted({b.text for b in decode_barcodes(final)} | {b.text for b in decode_barcodes(original)})
        rec = build_record(raw, barcodes, low_quality=pre.low_quality, provider=provider_name, page_number=job.number)
        _store_success(job, rec, raw, enhanced, barcodes)
    except Exception as exc:   # one bad page must not stop the batch
        _store_failure(page_id, exc)


async def process_document(document_id: uuid.UUID, providers: Providers | None = None) -> None:
    with session_scope() as s:
        page_ids = [p.id for p in s.get(Document, document_id).pages if p.status in ("pending", "error")]
    limit = asyncio.Semaphore(settings.max_concurrency)

    async def run(page_id: uuid.UUID) -> None:
        async with limit:
            await process_page(page_id, providers)

    await asyncio.gather(*(run(pid) for pid in page_ids))
