"""Fill the database with the sample forms WITHOUT calling a vision model, for a demo that cannot be stopped by
a daily quota or a blocked network.

Every sample page already has saved model answers in the evaluation caches. This replays one of them through the
REAL pipeline: the page is turned upright, enhanced, its barcodes are decoded, the answer is normalized and given
a confidence, and the record and images are stored exactly as for a live upload. Only the model call is replaced.

The records say so: their provider reads "gemini:gemini-2.5-flash (saved answer)". They are saved results, not a
live run, and anyone showing them should say that.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2

from app.db.session import session_scope
from app.evaluation import cache_tag
from app.pipeline.orientation import is_sideways
from app.pipeline.process import process_page
from app.schemas import RawExtraction
from app.services.documents import register_upload
from app.storage import get_storage


@dataclass(frozen=True)
class Source:
    """One cache of saved answers: which model, and whether its pages were turned upright before it read them."""
    provider: str
    model: str
    oriented: bool

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model} (saved answer)"


def parse_source(spec: str) -> Source:
    """`provider:model` (read with orientation correction) or `provider:model:raw` (read without it)."""
    parts = spec.split(":")
    if len(parts) not in (2, 3) or (len(parts) == 3 and parts[2] != "raw") or not all(parts[:2]):
        raise ValueError(f"'{spec}' should look like provider:model or provider:model:raw")
    return Source(parts[0], parts[1], oriented=len(parts) == 2)


# Best measured first (PLAN 10.2). The first gemini-2.5-flash answers were saved without orientation correction, so
# they are used for upright pages only; sideways pages take an answer that was read after the page was turned.
DEFAULT_SOURCES = (
    Source("gemini", "gemini-2.5-flash", oriented=False),
    Source("gemini", "gemini-2.5-flash", oriented=True),       # the held-out pages, read by the full pipeline
    Source("gemini", "gemini-3.5-flash", oriented=True),
    Source("groq", "qwen/qwen3.8-27b", oriented=True),
)


class ReplayProvider:
    """Stands in for a vision model by replaying a saved answer. For a page that needs flipping after its quarter
    turn, the first call says "upside down", exactly as a real model would, so the pipeline flips the page."""

    def __init__(self, raw: RawExtraction, label: str, upside_down_first: bool = False):
        self.name = label
        self._raw = raw
        self._say_upside_down = upside_down_first
        self.calls = 0

    async def extract(self, img, hint: str = "") -> RawExtraction:
        self.calls += 1
        if self._say_upside_down and self.calls == 1:
            return RawExtraction(text_upside_down=True)
        return self._raw


def load_flip_pages(path: Path) -> set[str]:
    """Sample scans that are still upside down after the quarter turn. Checked by eye on the 48 samples, and used
    only to show the page the right way up in the seeded demo."""
    if not path.is_file():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")).get("flip_after_turn", []))


def choose_answer(page: str, sideways: bool, sources: tuple[Source, ...], cache_root: Path) -> tuple[Source, RawExtraction] | None:
    """The first saved answer for this page, in the order given. An answer read from a page that was NOT turned
    is useless for a sideways page, so those are skipped."""
    for source in sources:
        if sideways and not source.oriented:
            continue
        saved = cache_root / cache_tag(source.provider, source.model, source.oriented) / f"{page}.json"
        if saved.is_file():
            return source, RawExtraction.model_validate_json(saved.read_text(encoding="utf-8"))
    return None


@dataclass
class SeedReport:
    seeded: list[str] = field(default_factory=list)
    already_there: list[str] = field(default_factory=list)       # the same page was uploaded before
    no_saved_answer: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    by_source: dict[str, int] = field(default_factory=dict)


async def seed_demo(pages_dir: Path, cache_root: Path, *, sources: tuple[Source, ...] = DEFAULT_SOURCES,
                    flip_pages: set[str] | None = None, pages: list[str] | None = None, limit: int | None = None,
                    dry_run: bool = False) -> SeedReport:
    """Seed one page at a time, in name order. Safe to run again: a page already uploaded is left as it is."""
    flip_pages = flip_pages or set()
    report = SeedReport()
    names = sorted(p.stem for p in pages_dir.glob("*.png"))
    if pages:
        names = [n for n in names if n in set(pages)]
    if limit:
        names = names[:limit]

    for name in names:
        image_file = pages_dir / f"{name}.png"
        sideways = is_sideways(cv2.cvtColor(cv2.imread(str(image_file)), cv2.COLOR_BGR2GRAY))
        chosen = choose_answer(name, sideways, sources, cache_root)
        if chosen is None:
            report.no_saved_answer.append(name)
            continue
        source, raw = chosen
        if dry_run:
            report.seeded.append(name)
            report.by_source[source.label] = report.by_source.get(source.label, 0) + 1
            continue

        with session_scope() as db:
            doc, duplicate = register_upload(db, get_storage(), image_file.name, image_file.read_bytes())
            page_id = doc.pages[0].id
        if duplicate:
            report.already_there.append(name)
            continue
        provider = ReplayProvider(raw, source.label, upside_down_first=sideways and name in flip_pages)
        await process_page(page_id, (provider, None))

        with session_scope() as db:
            ok = db.get(type(doc.pages[0]), page_id).status == "ready"
        (report.seeded if ok else report.failed).append(name)
        if ok:
            report.by_source[source.label] = report.by_source.get(source.label, 0) + 1
    return report
