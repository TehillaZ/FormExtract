"""The real API for browser tests (frontend/e2e).

Same app, same pipeline, same database code as production, with three differences so tests are fast,
repeatable and cannot touch real data or spend vision-API quota:
  * the database is in memory (SQLite) and images go to a temporary folder;
  * the vision model is replaced by a scripted provider whose answer depends only on the uploaded image's width;
  * POST /__test__/reset empties everything between tests, and POST /__test__/seed adds many records at once.
    Both exist only in this module;
  * the accuracy screen reads two saved reports from a temporary folder instead of the real data/ directory.

Run:  python -m uvicorn e2e.server:app --port 8100
"""
from __future__ import annotations

import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from app.api.main import app, get_evaluation_store
from app.db import repo
from app.db.models import Base
from app.db.session import init_db
from app.evaluation import EvaluationStore, FieldStats, build_report, save_report
from app.pipeline.extract import build_record
from app.schemas import RawExtraction, RawValue as V
from app.storage import LocalStorage, set_storage

storage_dir = Path(tempfile.mkdtemp(prefix="formextract-e2e-"))
db_dir = Path(tempfile.mkdtemp(prefix="formextract-e2e-db-"))          # apart from the images, which reset() clears
engine = init_db(f"sqlite:///{db_dir / 'e2e.db'}")   # a file, not memory: concurrent requests need their own connections
set_storage(LocalStorage(storage_dir))


def form_a() -> RawExtraction:
    """Printed names, a verified ID and sender; the rest is read but unverified."""
    return RawExtraction(
        template="clalit",
        first_name=V(value="דנה", source="printed"), last_name=V(value="כהן", source="printed"),
        id_numbers=[V(value="011223344", source="printed", highlighted=True)],   # the form points at it: verified
        central_numbers=[V(value="939376", source="sticker")],
        stamp_date=V(value="18/06/2026", source="stamp"),
        sender=V(value="כללית", source="printed", highlighted=True),
        commitment_numbers=[V(value="730578626", source="printed")],
    )


def form_b() -> RawExtraction:
    """Handwritten, with an invalid 10-digit ID and the SAME commitment number as form A."""
    return RawExtraction(
        template="hospital_screenshot",
        first_name=V(value="רונן", source="handwritten"), last_name=V(value="פלג", source="handwritten"),
        id_numbers=[V(value="0011223344", source="handwritten")],
        central_numbers=[V(value="939158", source="handwritten")],
        handwritten_date=V(value="16/06/2026", source="handwritten"),
        sender=V(value="מכבי", source="printed", highlighted=True),
        commitment_numbers=[V(value="730578626", source="printed")],
    )


def form_c() -> RawExtraction:
    """Almost nothing found, and a sender that is not on the list."""
    return RawExtraction(template="other", sender=V(value="קליניקה לא ידועה", source="printed"))


def form_d() -> RawExtraction:
    """The page that carries an orientation marker (see ScriptedProvider)."""
    return RawExtraction(
        template="clalit",
        first_name=V(value="יעל", source="printed"), last_name=V(value="אדם", source="printed"),
        id_numbers=[V(value="011223344", source="printed", highlighted=True)],
        central_numbers=[V(value="939001", source="sticker")],
        stamp_date=V(value="20/06/2026", source="stamp"),
        sender=V(value="כללית", source="printed", highlighted=True),
        commitment_numbers=[V(value="810000001", source="printed")],
    )


SCENARIOS = {600: form_a, 610: form_b, 620: form_c, 630: form_d}
MARKER_ROWS = 200       # form D carries a solid black block in its upright top-left corner
MARKER_DARK = 20


class ScriptedProvider:
    """Answers by the width of the page image: 600 -> form A, 610 -> form B, 620 -> form C, 630 -> form D.

    Form D also plays the part of the vision model judging orientation: if the black marker is in the bottom
    rows the page is upside down, and the answer is only `text_upside_down=True`. The pipeline must then flip
    the page and ask again, and the second answer is the full form."""

    name = "scripted"

    def __init__(self) -> None:
        self.calls = 0

    async def extract(self, img, hint: str = "") -> RawExtraction:
        self.calls += 1
        width = img.shape[1]
        if width == 630:
            dark_top = int((img[:MARKER_ROWS] < MARKER_DARK).sum())
            dark_bottom = int((img[-MARKER_ROWS:] < MARKER_DARK).sum())
            if dark_bottom > dark_top:
                return RawExtraction(text_upside_down=True)
        return SCENARIOS.get(width, form_c)()


provider = ScriptedProvider()
app.state.providers = (provider, None)


# ---- the accuracy screen: two saved reports, and a ground truth of 10 pages (8 development, 2 held out) ----------

def _stats(**fields: tuple[int, int, int, int]) -> dict[str, FieldStats]:
    return {name: FieldStats(*numbers) for name, numbers in fields.items()}


_workdir = Path(tempfile.mkdtemp(prefix="formextract-e2e-eval-"))
_reports_dir = _workdir / "reports"
for _model, _prompt, _id_stats, _day in (("model-a", "abc123", (8, 3, 5, 2), 20), ("model-b", "def456", (8, 5, 4, 0), 19)):
    _report = build_report(
        tag=f"gemini-{_model}-{_prompt}", provider="gemini", model=_model, prompt_id=_prompt, oriented=True,
        checksum_mode="strict", split="dev", pages_scored=8, pages_failed=0, pages=[f"p{i}" for i in range(8)],
        stats=_stats(id_number=_id_stats, central_numbers=(8, 6, 3, 0), received_date=(8, 4, 7, 0),
                     sender=(8, 6, 2, 0), commitment_numbers=(8, 7, 3, 1)))
    _report.created_at = datetime(2026, 10, _day, 12, 0, tzinfo=UTC)   # fixed, so model-a is always the newest
    save_report(_report, _reports_dir)
# a third report on only four of those pages: comparing it with the others would not be fair
_short = build_report(
    tag="gemini-model-c-aaa111", provider="gemini", model="model-c", prompt_id="aaa111", oriented=True,
    checksum_mode="strict", split="dev", pages_scored=4, pages_failed=0, pages=[f"p{i}" for i in range(4)],
    stats=_stats(id_number=(4, 4, 0, 0), central_numbers=(4, 3, 1, 0), received_date=(4, 2, 3, 0),
                 sender=(4, 4, 0, 0), commitment_numbers=(4, 3, 1, 0)))
_short.created_at = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
save_report(_short, _reports_dir)
(_workdir / "truth.jsonl").write_text("\n".join(json.dumps({"page": f"p{i}"}) for i in range(10)), encoding="utf-8")
(_workdir / "split.json").write_text(json.dumps({"dev": [f"p{i}" for i in range(8)], "test": ["p8", "p9"]}), encoding="utf-8")
app.dependency_overrides[get_evaluation_store] = lambda: EvaluationStore(
    _reports_dir, _workdir / "truth.jsonl", _workdir / "split.json")


@app.post("/__test__/seed")
def seed(n: int = 30, approved: int = 0) -> dict:
    """Add `n` records named דמה00, דמה01 ... straight into the database; the first `approved` are approved."""
    from app.db.session import session_scope
    with session_scope() as s:
        for i in range(n):
            raw = RawExtraction(
                first_name=V(value=f"דמה{i:02d}", source="printed"), last_name=V(value="בדיקה", source="printed"),
                id_numbers=[V(value=f"0{i:08d}", source="printed")],
                commitment_numbers=[V(value=f"90{i:07d}", source="printed")],
                sender=V(value="כללית" if i % 2 == 0 else "מכבי", source="printed", highlighted=True),
                stamp_date=V(value="18/06/2026", source="stamp"))
            rec = repo.save_record(s, build_record(raw, []))
            if i < approved:
                repo.approve_record(s, rec.id)
    return {"ok": True, "n": n}


@app.get("/__test__/calls")
def calls() -> dict:
    """How many times the vision model was asked, to check the call budget."""
    return {"calls": provider.calls}


@app.post("/__test__/reset")
def reset() -> dict:
    provider.calls = 0
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    for child in storage_dir.iterdir():
        shutil.rmtree(child, ignore_errors=True)
    return {"ok": True}
