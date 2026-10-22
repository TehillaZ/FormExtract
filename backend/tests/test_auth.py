import pytest
from fastapi.testclient import TestClient

import app.db.session as session_mod
from app.api.main import app
from app.config import settings
from app.evaluation import EvaluationStore


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "user_password", "user-pw")
    monkeypatch.setattr(settings, "developer_password", "dev-pw")
    session_mod.init_db("sqlite://")
    from app.api.main import get_evaluation_store
    app.dependency_overrides[get_evaluation_store] = lambda: EvaluationStore(tmp_path / "r", tmp_path / "t.jsonl", tmp_path / "s.json")
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_evaluation_store, None)


def login(client, password):
    return client.post("/auth/login", json={"password": password})


def test_nothing_is_open_without_logging_in(client):
    for path in ("/records", "/senders", "/pages/active", "/auth/me", "/evaluation", "/corrections/summary"):
        assert client.get(path).status_code == 401, path
    assert client.get("/health").status_code == 200


def test_wrong_password(client):
    assert login(client, "nope").status_code == 401
    assert login(client, "").status_code == 401
    assert client.get("/records").status_code == 401


def test_user_sees_the_forms_but_not_the_developer_screens(client):
    assert login(client, "user-pw").json() == {"role": "user"}
    assert client.get("/auth/me").json() == {"role": "user"}
    assert client.get("/records").status_code == 200
    assert client.get("/evaluation").status_code == 403
    assert client.get("/corrections/summary").status_code == 403


def test_developer_sees_everything(client):
    assert login(client, "dev-pw").json() == {"role": "developer"}
    assert client.get("/records").status_code == 200
    assert client.get("/evaluation").status_code == 200
    assert client.get("/corrections/summary").status_code == 200


def test_logout(client):
    login(client, "user-pw")
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/records").status_code == 401


def test_a_forged_cookie_is_refused(client):
    client.cookies.set("session", "developer." + "0" * 64)
    assert client.get("/evaluation").status_code == 401
    client.cookies.set("session", "user.whatever")
    assert client.get("/records").status_code == 401


def test_a_cookie_stops_working_when_the_password_changes(client, monkeypatch):
    login(client, "dev-pw")
    monkeypatch.setattr(settings, "developer_password", "changed")
    assert client.get("/evaluation").status_code == 401


def test_a_role_without_a_password_cannot_log_in(client, monkeypatch):
    monkeypatch.setattr(settings, "developer_password", "")
    assert login(client, "").status_code == 401
    client.cookies.set("session", "developer." + "0" * 64)
    assert client.get("/evaluation").status_code == 401
