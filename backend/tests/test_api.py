"""API tests with a fake vision provider: no network, no quota."""

import uuid

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

import app.db.session as session_mod
from app.api.main import app
from app.db.models import Page
from app.pipeline.process import extract_with_fallback, process_page
from app.schemas import RawExtraction, RawValue as V
from app.storage import LocalStorage, set_storage
from app.vision import RateLimited


class FakeProvider:
    def __init__(self, name="fake", answers=None, fail=None):
        self.name, self.answers, self.fail, self.calls = name, answers or {}, fail, 0

    async def extract(self, img, hint=""):
        self.calls += 1
        if self.fail:
            raise self.fail
        n = self.calls
        return RawExtraction(
            sender=V(value="כללית", source="printed", highlighted=True),
            stamp_date=V(value="18/06/2026", source="stamp"),
            id_numbers=[V(value="011223344", source="printed")],
            central_numbers=[V(value=f"93{n:04d}", source="sticker")],
            commitment_numbers=[V(value=f"7305{n:05d}", source="printed")],
        )


def png_bytes(w=300, h=400) -> bytes:
    img = np.full((h, w, 3), 255, np.uint8)
    cv2.putText(img, "form", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
    return cv2.imencode(".png", img)[1].tobytes()


@pytest.fixture()
def client(tmp_path):
    session_mod.init_db("sqlite://")
    set_storage(LocalStorage(tmp_path))
    app.state.providers = (FakeProvider(), None)
    with TestClient(app) as c:
        yield c
    app.state.providers = None


def upload(client, name="a.png", data=None):
    return client.post("/documents", files=[("files", (name, data or png_bytes(), "image/png"))])


def test_upload_processes_page_into_a_pending_record(client):
    r = upload(client)
    assert r.status_code == 202
    doc = client.get(f"/documents/{r.json()[0]['id']}").json()   # background task already ran in TestClient
    assert doc["done"] and doc["pages"][0]["status"] == "ready"
    rec = client.get(f"/records/{doc['pages'][0]['record_id']}").json()
    assert rec["status"] == "pending" and rec["provider"] == "fake"
    assert rec["received_date"]["value"] == "2026-06-18"
    assert rec["central_numbers"][0]["value"] == "930001"
    assert client.get(f"/pages/{doc['pages'][0]['id']}/image").headers["content-type"] == "image/png"


def test_identical_file_is_not_processed_twice(client):
    data = png_bytes()
    first = upload(client, data=data).json()[0]
    second = upload(client, data=data).json()[0]
    assert second["duplicate"] and second["id"] == first["id"]
    assert len(client.get("/records").json()) == 1


def test_bad_file_is_rejected(client):
    r = client.post("/documents", files=[("files", ("x.txt", b"hello", "text/plain"))])
    assert r.status_code == 400


def test_patch_approve_and_duplicate_conflict(client):
    for i in range(2):
        upload(client, name=f"{i}.png", data=png_bytes(300 + i))
    a, b = client.get("/records").json()
    # make b carry the same commitment number as a, then approve both
    num = a["commitment_numbers"][0]["value"]
    assert client.patch(f"/records/{b['id']}", json={"commitment_numbers": [num]}).status_code == 200
    assert client.post(f"/records/{a['id']}/approve").json()["status"] == "approved"
    r = client.post(f"/records/{b['id']}/approve")
    assert r.status_code == 409 and num in r.json()["detail"]


def test_patch_validation_error_is_422(client):
    upload(client)
    rid = client.get("/records").json()[0]["id"]
    assert client.patch(f"/records/{rid}", json={"central_numbers": ["12"]}).status_code == 422
    assert client.get("/records/00000000-0000-0000-0000-000000000000").status_code == 404


def test_approve_clean_only_approves_records_with_nothing_flagged(client):
    upload(client)
    rid = client.get("/records").json()[0]["id"]
    assert client.post("/records/approve-clean").json()["approved"] == []   # sender high, but others are not
    client.patch(f"/records/{rid}", json={"first_name": "דנה", "last_name": "כהן", "central_numbers": ["939376"],
                                           "commitment_numbers": ["730578626"], "id_number": "11223344",
                                           "received_date": "19/06/2026", "sender": "כללית"})
    assert client.post("/records/approve-clean").json()["approved"] == [rid]


def test_failed_page_can_be_reprocessed(client):
    app.state.providers = (FakeProvider(fail=RuntimeError("boom")), None)
    doc = upload(client).json()[0]
    page = client.get(f"/documents/{doc['id']}").json()["pages"][0]
    assert page["status"] == "error" and page["error"] == "RuntimeError"   # no field data in errors
    app.state.providers = (FakeProvider(), None)
    assert client.post(f"/pages/{page['id']}/reprocess").status_code == 202
    assert client.get(f"/documents/{doc['id']}").json()["pages"][0]["status"] == "ready"


@pytest.mark.asyncio
async def test_fallback_provider_used_only_after_rate_limit():
    primary = FakeProvider("gemini", fail=RateLimited("x"))
    fallback = FakeProvider("groq")
    raw, name = await extract_with_fallback(None, primary, fallback)
    assert name == "groq" and fallback.calls == 1
    ok_primary = FakeProvider("gemini")
    _, name = await extract_with_fallback(None, ok_primary, fallback)
    assert name == "gemini" and fallback.calls == 1


def test_senders_list(client):
    s = client.get("/senders").json()
    assert "כללית" in s and len(s) >= 50


def test_saving_a_flagged_field_unchanged_through_the_api_clears_its_flag(client):
    upload(client)
    rec = client.get("/records").json()[0]
    assert rec["received_date"]["confidence"] == "medium"
    out = client.patch(f"/records/{rec['id']}", json={"received_date": "18/06/2026"}).json()
    assert out["received_date"]["confidence"] == "high" and out["received_date"]["source"] == "manual"
    assert out["corrections"] == []


# ---- a processed page is never processed again --------------------------------------------------
# Its saved model answer is what the record's corrections were made against. A second run would replace the
# answer and create a second record, leaving the corrections tied to an answer that no longer exists.

def page_state(page_id: str) -> dict:
    with session_mod._factory() as s:
        page = s.get(Page, uuid.UUID(page_id))
        return {"status": page.status, "record_id": page.record_id, "raw": page.raw_extraction, "barcodes": page.barcodes}


def uploaded_page(client) -> dict:
    """Upload one form and return its page (id and record_id) once processed."""
    doc = upload(client).json()[0]
    return client.get(f"/documents/{doc['id']}").json()["pages"][0]


def test_a_processed_page_cannot_be_reprocessed_and_keeps_its_model_answer_and_corrections(client):
    provider = app.state.providers[0]
    page = uploaded_page(client)
    client.patch(f"/records/{page['record_id']}", json={"central_numbers": ["939999"]})   # a technician's correction
    before_state = page_state(page["id"])
    before_record = client.get(f"/records/{page['record_id']}").json()
    assert before_state["raw"] and before_record["corrections"]

    refused = client.post(f"/pages/{page['id']}/reprocess")

    assert refused.status_code == 409
    assert provider.calls == 1                                             # the model was not asked again
    assert page_state(page["id"]) == before_state                          # same record, same saved model answer
    assert client.get(f"/records/{page['record_id']}").json() == before_record   # corrections untouched
    assert len(client.get("/records").json()) == 1                         # no second record


@pytest.mark.asyncio
async def test_processing_a_page_that_already_has_a_record_does_nothing(client):
    provider = app.state.providers[0]
    page = uploaded_page(client)
    before = page_state(page["id"])

    await process_page(uuid.UUID(page["id"]), app.state.providers)   # the pipeline entry point, bypassing the API

    assert provider.calls == 1
    assert page_state(page["id"]) == before
    assert len(client.get("/records").json()) == 1


def test_a_failed_page_can_still_be_retried_and_ends_with_exactly_one_record(client):
    app.state.providers = (FakeProvider(fail=RuntimeError("boom")), None)
    page = uploaded_page(client)
    assert page["status"] == "error" and page["record_id"] is None

    app.state.providers = (FakeProvider(), None)
    assert client.post(f"/pages/{page['id']}/reprocess").status_code == 202

    retried = page_state(page["id"])
    assert retried["status"] == "ready" and retried["record_id"] is not None
    records = client.get("/records").json()
    assert [r["id"] for r in records] == [str(retried["record_id"])]


def test_a_page_that_is_being_processed_is_still_refused(client):
    app.state.providers = (FakeProvider(fail=RuntimeError("boom")), None)
    page = uploaded_page(client)
    with session_mod._factory() as s:
        s.get(Page, uuid.UUID(page["id"])).status = "processing"
        s.commit()
    refused = client.post(f"/pages/{page['id']}/reprocess")
    assert refused.status_code == 409 and "בעיבוד" in refused.json()["detail"]


def test_reprocessing_an_unknown_page_is_not_found(client):
    assert client.post(f"/pages/{uuid.uuid4()}/reprocess").status_code == 404


def test_a_document_without_pages_is_not_done():
    """A status read can catch a document before its pages exist; "done" must not be true for zero pages,
    or the screen stops polling and shows "0 of 0 pages" forever."""
    from app.api.schemas import DocumentStatus
    from app.db.models import Document
    status = DocumentStatus.of(Document(id=uuid.uuid4(), filename="x.png", file_hash="h", pages=[]))
    assert status.pages == [] and status.done is False


# ---- the form is visible before the fields are read ---------------------------------------------------------

class SeesTheFormFirst(FakeProvider):
    """While the model is still working, the page must already have an enhanced image and be in progress."""
    seen = None

    async def extract(self, img, hint=""):
        with session_mod.session_scope() as s:
            page = s.query(Page).one()
            self.seen = (page.status, page.record_id, page.image_path)
        return await super().extract(img, hint)


def test_the_page_image_is_stored_before_the_model_is_asked(client):
    provider = SeesTheFormFirst()
    app.state.providers = (provider, None)
    upload(client)
    status, record_id, image_path = provider.seen
    assert (status, record_id) == ("processing", None) and image_path.endswith("_enhanced.png")
    assert client.get("/pages/active").json() == []     # a finished page is a record, not "active"


def test_a_page_in_progress_is_listed_with_its_image(client):
    with session_mod._factory() as s:
        from app.db.models import Document
        doc = Document(filename="a.png", file_hash="x")
        doc.pages.append(Page(page_number=1, status="processing", original_path="o.png"))
        s.add(doc)
        s.commit()
    [p] = client.get("/pages/active").json()
    assert (p["status"], p["filename"], p["page_number"]) == ("processing", "a.png", 1)


def test_a_failed_page_stays_in_the_active_list_so_it_can_be_retried(client):
    app.state.providers = (FakeProvider(fail=RuntimeError("boom")), None)
    upload(client)
    [p] = client.get("/pages/active").json()
    assert p["status"] == "error" and p["error"] == "RuntimeError"
