"""API tests with a fake vision provider: no network, no quota."""
import io

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

import app.db.session as session_mod
from app.api.main import app
from app.pipeline.process import extract_with_fallback
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
