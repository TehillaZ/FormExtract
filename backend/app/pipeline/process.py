"""Background processing: page image -> enhanced image -> barcodes -> model -> record in the DB (ADR-005)."""
from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from app.config import settings
from app.db import repo
from app.db.models import Document, Page
from app.db.session import session_scope
from app.pipeline.barcodes import decode_barcodes
from app.pipeline.extract import build_record
from app.pipeline.preprocess import preprocess
from app.schemas import RawExtraction
from app.storage import get_storage
from app.vision import RateLimited, VisionProvider, get_provider

log = logging.getLogger(__name__)   # never log field values (PLAN 11)

PHOTO_EXTS = {".jpg", ".jpeg", ".heic", ".heif"}


def _provider_available(name: str) -> bool:
    return bool(getattr(settings, f"{name}_api_key"))


async def extract_with_fallback(img, primary: VisionProvider, fallback: VisionProvider | None) -> tuple[RawExtraction, str]:
    """The fallback provider sees a page only when the primary kept answering 429 (PLAN 11, ADR-003)."""
    try:
        return await primary.extract(img), primary.name
    except RateLimited:
        if fallback is None:
            raise
        return await fallback.extract(img), fallback.name


def _providers() -> tuple[VisionProvider, VisionProvider | None]:
    primary = get_provider(settings.vision_provider)
    fb_name = settings.vision_fallback_provider
    fallback = get_provider(fb_name) if fb_name != settings.vision_provider and _provider_available(fb_name) else None
    return primary, fallback


async def process_page(page_id: uuid.UUID, providers: tuple[VisionProvider, VisionProvider | None] | None = None) -> None:
    storage = get_storage()
    with session_scope() as s:
        page = s.get(Page, page_id)
        if page is None:
            return
        page.status, page.error = "processing", None
        s.commit()
        doc_id, number, original = page.document_id, page.page_number, page.original_path
        is_photo = Path(page.document.filename).suffix.lower() in PHOTO_EXTS
    try:
        primary, fallback = providers or _providers()
        img = storage.read_image(original)
        pre = preprocess(img, is_photo=is_photo)
        enhanced = storage.save_image(f"{doc_id}/{number}_enhanced.png", pre.image)
        codes = {b.text for b in decode_barcodes(pre.image)} | {b.text for b in decode_barcodes(img)}
        raw, provider_name = await extract_with_fallback(pre.image, primary, fallback)
        rec = build_record(raw, sorted(codes), low_quality=pre.low_quality, provider=provider_name, page_number=number)
        rec.document_id, rec.page_ids = doc_id, [page_id]
        with session_scope() as s:
            saved = repo.save_record(s, rec)
            page = s.get(Page, page_id)
            page.record_id, page.image_path, page.status = saved.id, enhanced, "ready"
            page.raw_extraction, page.barcodes = raw.model_dump(mode="json"), sorted(codes)
            s.commit()
    except Exception as e:   # one bad page must not stop the batch
        log.warning("page %s failed: %s", page_id, type(e).__name__)
        with session_scope() as s:
            page = s.get(Page, page_id)
            page.status, page.error = "error", f"{type(e).__name__}"
            s.commit()


async def process_document(document_id: uuid.UUID, providers=None) -> None:
    with session_scope() as s:
        ids = [p.id for p in s.get(Document, document_id).pages if p.status in ("pending", "error")]
    sem = asyncio.Semaphore(settings.max_concurrency)

    async def run(pid):
        async with sem:
            await process_page(pid, providers)

    await asyncio.gather(*(run(p) for p in ids))
