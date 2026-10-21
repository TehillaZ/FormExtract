"""Saved accuracy reports: what the accuracy screen shows, and what it must say was NOT run."""
import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import app.db.session as session_mod
from app.api.main import app, get_evaluation_store
from app.evaluation import EvaluationReport, EvaluationStore, FieldStats, build_report, load_reports, save_report


def stats(**per_field) -> dict[str, FieldStats]:
    """stats(sender=(pages, correct, flagged, silent)) ..."""
    return {name: FieldStats(*vals) for name, vals in per_field.items()}


def report(tag="gemini-m-abc", split="dev", **over) -> EvaluationReport:
    base = dict(tag=tag, provider="gemini", model="m", prompt_id="abc", oriented=True, checksum_mode="strict",
                split=split, pages_scored=21, pages_failed=0,
                stats=stats(id_number=(21, 7, 11, 4), sender=(21, 14, 7, 0)))
    return build_report(**{**base, **over})


class TestBuildSaveLoad:
    def test_a_report_carries_the_numbers_it_was_given(self):
        r = report()
        assert r.fields["id_number"].model_dump() == {"pages": 21, "correct": 7, "flagged": 11, "silent_errors": 4}
        assert (r.provider, r.model, r.prompt_id, r.split, r.pages_scored) == ("gemini", "m", "abc", "dev", 21)

    def test_save_then_load_roundtrips(self, tmp_path):
        save_report(report(), tmp_path)
        (loaded,) = load_reports(tmp_path)
        assert loaded.fields["sender"].correct == 14 and loaded.oriented is True and loaded.split == "dev"

    def test_running_the_same_configuration_again_replaces_the_report(self, tmp_path):
        save_report(report(pages_scored=10), tmp_path)
        save_report(report(pages_scored=21), tmp_path)
        assert [r.pages_scored for r in load_reports(tmp_path)] == [21]

    def test_dev_and_test_results_of_one_configuration_are_kept_apart(self, tmp_path):
        save_report(report(split="dev"), tmp_path)
        save_report(report(split="test"), tmp_path)
        assert sorted(r.split for r in load_reports(tmp_path)) == ["dev", "test"]

    def test_newest_first(self, tmp_path):
        old = report(tag="old")
        old.created_at = datetime.now(UTC) - timedelta(days=2)
        save_report(old, tmp_path)
        save_report(report(tag="new"), tmp_path)
        assert [r.tag for r in load_reports(tmp_path)] == ["new", "old"]

    def test_a_broken_file_is_skipped_not_fatal(self, tmp_path):
        save_report(report(), tmp_path)
        (tmp_path / "garbage.json").write_text("{not json", encoding="utf-8")
        (tmp_path / "wrong-shape.json").write_text(json.dumps({"hello": 1}), encoding="utf-8")
        (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
        assert len(load_reports(tmp_path)) == 1

    def test_a_missing_folder_means_no_reports(self, tmp_path):
        assert load_reports(tmp_path / "nope") == []


class TestCoverage:
    def store(self, tmp_path, truth_pages=4, split=None):
        truth = tmp_path / "truth.jsonl"
        truth.write_text("\n".join(json.dumps({"page": f"p{i}"}) for i in range(truth_pages)), encoding="utf-8")
        split_file = tmp_path / "split.json"
        if split is not None:
            split_file.write_text(json.dumps(split), encoding="utf-8")
        return EvaluationStore(reports_dir=tmp_path / "reports", truth_file=truth, split_file=split_file)

    def test_counts_the_verified_pages_and_the_held_out_test_pages(self, tmp_path):
        c = self.store(tmp_path, 4, {"dev": ["p0", "p1", "p2"], "test": ["p3"]}).coverage()
        assert (c.pages, c.dev, c.test) == (4, 3, 1)

    def test_without_a_split_everything_counts_as_development(self, tmp_path):
        c = self.store(tmp_path, 4).coverage()
        assert (c.pages, c.dev, c.test) == (4, 4, 0)

    def test_without_ground_truth_everything_is_zero(self, tmp_path):
        c = EvaluationStore(reports_dir=tmp_path, truth_file=tmp_path / "x", split_file=tmp_path / "y").coverage()
        assert (c.pages, c.dev, c.test) == (0, 0, 0)


class TestEndpoint:
    @pytest.fixture()
    def client(self):
        session_mod.init_db("sqlite://")
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()

    def serve(self, store):
        app.dependency_overrides[get_evaluation_store] = lambda: store

    def test_returns_the_reports_with_the_coverage(self, client, tmp_path):
        save_report(report(), tmp_path / "reports")
        truth = tmp_path / "truth.jsonl"
        truth.write_text("\n".join(json.dumps({"page": f"p{i}"}) for i in range(5)), encoding="utf-8")
        split = tmp_path / "split.json"
        split.write_text(json.dumps({"dev": ["p0", "p1", "p2"], "test": ["p3", "p4"]}), encoding="utf-8")
        self.serve(EvaluationStore(tmp_path / "reports", truth, split))

        body = client.get("/evaluation").json()

        assert (body["pages"], body["dev_pages"], body["test_pages"]) == (5, 3, 2)
        (only,) = body["reports"]
        assert only["fields"]["id_number"] == {"pages": 21, "correct": 7, "flagged": 11, "silent_errors": 4}
        assert only["model"] == "m" and only["split"] == "dev" and only["oriented"] is True

    def test_no_reports_is_a_normal_answer(self, client, tmp_path):
        self.serve(EvaluationStore(tmp_path / "none", tmp_path / "t", tmp_path / "s"))
        assert client.get("/evaluation").json() == {"reports": [], "pages": 0, "dev_pages": 0, "test_pages": 0}


class TestPagesCovered:
    def test_a_report_records_which_pages_it_scored_sorted(self):
        r = report(pages=["p3", "p1", "p2"], pages_scored=3)
        assert r.pages == ["p1", "p2", "p3"]

    def test_pages_survive_saving_and_loading(self, tmp_path):
        save_report(report(pages=["p1", "p2"], pages_scored=2), tmp_path)
        assert load_reports(tmp_path)[0].pages == ["p1", "p2"]

    def test_a_report_written_before_pages_were_recorded_still_loads_with_none_listed(self, tmp_path):
        old = json.loads(report().model_dump_json())
        del old["pages"]
        (tmp_path / "old.json").write_text(json.dumps(old), encoding="utf-8")
        assert load_reports(tmp_path)[0].pages == []
