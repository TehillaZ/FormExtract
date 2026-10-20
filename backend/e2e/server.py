"""The real API for browser tests (frontend/e2e).

Same app, same pipeline, same database code as production, with three differences so tests are fast,
repeatable and cannot touch real data or spend vision-API quota:
  * the database is in memory (SQLite) and images go to a temporary folder;
  * the vision model is replaced by a scripted provider whose answer depends only on the uploaded image's width;
  * POST /__test__/reset empties everything between tests. This endpoint exists only in this module.

Run:  python -m uvicorn e2e.server:app --port 8100
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from app.api.main import app
from app.db.models import Base
from app.db.session import init_db
from app.schemas import RawExtraction, RawValue as V
from app.storage import LocalStorage, set_storage

engine = init_db("sqlite://")
storage_dir = Path(tempfile.mkdtemp(prefix="formextract-e2e-"))
set_storage(LocalStorage(storage_dir))


def form_a() -> RawExtraction:
    """Printed names, a verified ID and sender; the rest is read but unverified."""
    return RawExtraction(
        template="clalit",
        first_name=V(value="דנה", source="printed"), last_name=V(value="כהן", source="printed"),
        id_numbers=[V(value="011223344", source="printed")],
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
        id_numbers=[V(value="011223344", source="printed")],
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
