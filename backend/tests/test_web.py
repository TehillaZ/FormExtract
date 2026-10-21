"""The single server for running and demoing: interface at /, API at /api."""
import pytest
from fastapi.testclient import TestClient

import app.db.session as session_mod
from app.web import create_web_app


@pytest.fixture()
def dist(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>FormExtract UI</title><div id=root></div>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log('ui')", encoding="utf-8")
    (tmp_path.parent / "secret.txt").write_text("do not serve", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def client(dist):
    session_mod.init_db("sqlite://")
    with TestClient(create_web_app(dist)) as c:
        yield c


class TestInterface:
    def test_the_root_serves_the_interface(self, client):
        r = client.get("/")
        assert r.status_code == 200 and "FormExtract UI" in r.text and r.headers["content-type"].startswith("text/html")

    def test_assets_are_served(self, client):
        r = client.get("/assets/app.js")
        assert r.status_code == 200 and "console.log" in r.text

    def test_any_other_path_serves_the_interface_so_a_reload_works(self, client):
        for path in ("/records", "/some/deep/page"):
            r = client.get(path)
            assert r.status_code == 200 and "FormExtract UI" in r.text

    def test_files_outside_the_interface_folder_are_never_served(self, client):
        for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"):
            assert "do not serve" not in client.get(path).text


class TestApi:
    def test_the_api_lives_under_api(self, client):
        assert client.get("/api/health").json() == {"ok": True}

    def test_the_records_list_and_its_total_work_through_the_mount(self, client):
        r = client.get("/api/records")
        assert r.status_code == 200 and r.json() == [] and r.headers["x-total-count"] == "0"

    def test_an_unknown_api_path_is_a_json_404_not_the_interface(self, client):
        r = client.get("/api/nope")
        assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
        assert "FormExtract UI" not in r.text


class TestNotBuilt:
    def test_without_a_built_interface_it_says_how_to_build_it_and_the_api_still_works(self, tmp_path):
        session_mod.init_db("sqlite://")
        with TestClient(create_web_app(tmp_path / "missing")) as c:
            r = c.get("/")
            assert r.status_code == 503 and "npm run build" in r.text
            assert c.get("/api/health").json() == {"ok": True}
