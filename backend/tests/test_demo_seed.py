"""Seeding the demo from saved model answers, through the real pipeline and without any model."""
import json
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

import app.db.session as session_mod
from app.db import repo
from app.db.models import Document, Page
from app.evaluation import cache_tag
from app.schemas import RawExtraction, RawValue as V
from app.services.demo_seed import DEFAULT_SOURCES, SAVED_PROMPT, ReplayProvider, Source, load_flip_pages, parse_source, seed_demo
from app.storage import LocalStorage, get_storage, set_storage

RAW = Source("gemini", "gemini-2.5-flash", oriented=False)       # answers saved from pages that were not turned
TURNED = Source("groq", "qwen/qwen3.8-27b", oriented=True)       # answers saved from pages that were turned upright first
OTHER = Source("gemini", "gemini-3.5-flash", oriented=True)


@pytest.fixture()
def env(tmp_path):
    session_mod.init_db("sqlite://")
    set_storage(LocalStorage(tmp_path / "storage"))
    pages, cache = tmp_path / "pages", tmp_path / "cache"
    pages.mkdir()
    return SimpleNamespace(pages=pages, cache=cache)


def upright_page(label: str, width: int = 600) -> np.ndarray:
    """Rows of text, like a typed form, so it is not mistaken for a sideways scan. The label makes each page unique."""
    img = np.full((800, width, 3), 255, np.uint8)
    cv2.putText(img, label, (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (30, 30, 30), 2, cv2.LINE_AA)
    for row in range(14):
        for col in range(5):
            cv2.putText(img, "abc 123", (30 + col * 105, 130 + row * 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (60, 60, 60), 1, cv2.LINE_AA)
    return img


def marked(label: str) -> np.ndarray:
    img = upright_page(label)
    cv2.rectangle(img, (10, 10), (110, 110), (0, 0, 0), -1)         # a black block marks the top-left of an upright page
    return img


def add_page(env, name: str, image: np.ndarray) -> None:
    cv2.imwrite(str(env.pages / f"{name}.png"), image)


def add_answer(env, name: str, source: Source, **fields) -> None:
    folder = env.cache / cache_tag(source.provider, source.model, source.oriented)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(RawExtraction(**fields).model_dump_json(), encoding="utf-8")


def answer_for(first: str, central: str = "939376") -> dict:
    return dict(first_name=V(value=first, source="printed"), central_numbers=[V(value=central, source="sticker")],
                sender=V(value="כללית", source="printed", highlighted=True))


def records() -> list:
    with session_mod._factory() as s:
        return repo.list_records(s)


def stored_image(page_id) -> np.ndarray:
    with session_mod._factory() as s:
        return get_storage().read_image(s.get(Page, page_id).image_path)


async def seed(env, *, sources=(RAW,), **kw):
    return await seed_demo(env.pages, env.cache, sources=sources, **kw)


class TestSeeding:
    async def test_a_page_is_seeded_from_its_saved_answer_through_the_real_pipeline(self, env):
        add_page(env, "p1", upright_page("P1"))
        add_answer(env, "p1", RAW, **answer_for("דנה"))

        report = await seed(env)

        assert report.seeded == ["p1"] and not report.failed
        (rec,) = records()
        assert rec.first_name.value == "דנה"
        assert rec.sender.value == "כללית" and rec.sender.confidence == "high"      # the real rules ran on it
        assert rec.central_numbers[0].value == "939376" and rec.status == "pending"
        with session_mod._factory() as s:
            page = s.query(Page).one()
            assert page.status == "ready" and page.record_id == rec.id and page.raw_extraction["first_name"]["value"] == "דנה"
            assert get_storage().read_image(page.image_path).shape[:2] == (800, 600)    # the enhanced image was stored

    async def test_the_record_says_it_is_a_saved_answer_and_which_model(self, env):
        add_page(env, "p1", upright_page("P1"))
        add_answer(env, "p1", RAW, **answer_for("דנה"))
        await seed(env)
        assert records()[0].provider == "gemini:gemini-2.5-flash (saved answer)"

    async def test_a_page_with_no_saved_answer_is_reported_and_not_seeded(self, env):
        add_page(env, "p1", upright_page("P1"))
        add_page(env, "p2", upright_page("P2"))
        add_answer(env, "p1", RAW, **answer_for("דנה"))
        report = await seed(env)
        assert (report.seeded, report.no_saved_answer) == (["p1"], ["p2"])
        assert len(records()) == 1

    async def test_running_it_again_changes_nothing(self, env):
        add_page(env, "p1", upright_page("P1"))
        add_answer(env, "p1", RAW, **answer_for("דנה"))
        await seed(env)
        again = await seed(env)
        assert again.seeded == [] and again.already_there == ["p1"]
        assert len(records()) == 1
        with session_mod._factory() as s:
            assert s.query(Document).count() == 1

    async def test_a_dry_run_changes_nothing(self, env):
        add_page(env, "p1", upright_page("P1"))
        add_answer(env, "p1", RAW, **answer_for("דנה"))
        report = await seed(env, dry_run=True)
        assert report.seeded == ["p1"] and report.by_source == {RAW.label: 1}
        assert records() == []
        with session_mod._factory() as s:
            assert s.query(Document).count() == 0

    async def test_a_page_the_pipeline_could_not_finish_is_reported_as_failed_not_as_seeded(self, env, monkeypatch):
        add_page(env, "p1", upright_page("P1"))
        add_answer(env, "p1", RAW, **answer_for("דנה"))

        async def gives_up(page_id, providers):          # the pipeline leaves the page unfinished
            return None

        monkeypatch.setattr("app.services.demo_seed.process_page", gives_up)
        report = await seed(env)
        assert report.failed == ["p1"] and report.seeded == [] and report.by_source == {}

    async def test_the_pages_and_limit_options_choose_what_is_seeded(self, env):
        for name in ("p1", "p2", "p3"):
            add_page(env, name, upright_page(name.upper()))
            add_answer(env, name, RAW, **answer_for(name))
        assert (await seed(env, pages=["p2"])).seeded == ["p2"]                   # only the named page
        assert (await seed(env, limit=1)).seeded == ["p1"]                        # the first page by name, p2 is already there
        assert (await seed(env, pages=["p3"], limit=5)).seeded == ["p3"]
        assert sorted(r.first_name.value for r in records()) == ["p1", "p2", "p3"]


class TestWhichSavedAnswer:
    async def test_the_first_source_that_has_the_page_wins_and_later_ones_fill_the_gaps(self, env):
        for name in ("p1", "p2"):
            add_page(env, name, upright_page(name.upper()))
        add_answer(env, "p1", RAW, **answer_for("מהראשון"))
        add_answer(env, "p1", TURNED, **answer_for("מהשני"))
        add_answer(env, "p2", TURNED, **answer_for("רק בשני"))

        report = await seed(env, sources=(RAW, TURNED))

        assert report.by_source == {RAW.label: 1, TURNED.label: 1}
        by_name = {r.first_name.value: r for r in records()}
        assert set(by_name) == {"מהראשון", "רק בשני"}
        assert by_name["מהראשון"].provider == RAW.label and by_name["רק בשני"].provider == TURNED.label

    async def test_a_sideways_page_never_uses_an_answer_read_from_the_unturned_page(self, env):
        add_page(env, "s1", cv2.rotate(upright_page("S1"), cv2.ROTATE_90_COUNTERCLOCKWISE))
        add_answer(env, "s1", RAW, **answer_for("מהדף המסתובב"))
        assert (await seed(env, sources=(RAW,))).no_saved_answer == ["s1"]

        add_answer(env, "s1", TURNED, **answer_for("אחרי הסיבוב"))
        assert (await seed(env, sources=(RAW, TURNED))).seeded == ["s1"]
        (rec,) = records()
        assert rec.first_name.value == "אחרי הסיבוב"
        assert stored_image(rec.page_ids[0]).shape[:2] == (800, 600)    # shown upright (portrait), not as the 800 x 600 scan

    async def test_an_upright_page_may_use_a_raw_answer(self, env):
        add_page(env, "p1", upright_page("P1"))
        add_answer(env, "p1", RAW, **answer_for("דנה"))
        assert (await seed(env, sources=(RAW,))).seeded == ["p1"]


class TestOrientation:
    def top_left_is_dark(self, image: np.ndarray) -> bool:
        return float(image[60, 60].mean()) < 40

    async def test_a_page_that_is_upside_down_after_the_turn_is_flipped_so_the_reviewer_sees_it_upright(self, env):
        add_page(env, "f1", cv2.rotate(marked("F1"), cv2.ROTATE_90_CLOCKWISE))   # turned, then still upside down
        add_answer(env, "f1", TURNED, **answer_for("הפוך"))

        await seed(env, sources=(TURNED,), flip_pages={"f1"})

        (rec,) = records()
        assert rec.first_name.value == "הפוך"
        assert self.top_left_is_dark(stored_image(rec.page_ids[0]))              # the marker is back at the top

    async def test_without_the_flip_note_such_a_page_stays_upside_down(self, env):
        add_page(env, "f1", cv2.rotate(marked("F1"), cv2.ROTATE_90_CLOCKWISE))
        add_answer(env, "f1", TURNED, **answer_for("הפוך"))
        await seed(env, sources=(TURNED,), flip_pages=set())
        assert not self.top_left_is_dark(stored_image(records()[0].page_ids[0]))

    async def test_the_flip_note_is_ignored_for_a_page_that_is_not_sideways(self, env):
        add_page(env, "p1", marked("P1"))
        add_answer(env, "p1", RAW, **answer_for("דנה"))
        await seed(env, sources=(RAW,), flip_pages={"p1"})
        assert self.top_left_is_dark(stored_image(records()[0].page_ids[0]))     # not flipped

    async def test_the_replay_provider_says_upside_down_once_and_then_gives_the_saved_answer(self):
        saved = RawExtraction(**answer_for("דנה"))
        provider = ReplayProvider(saved, "x", upside_down_first=True)
        first, second, third = await provider.extract(None), await provider.extract(None), await provider.extract(None)
        assert first.text_upside_down and not second.text_upside_down and second.first_name.value == "דנה"
        assert third.first_name.value == "דנה" and provider.calls == 3

    async def test_a_plain_replay_provider_never_claims_upside_down(self):
        provider = ReplayProvider(RawExtraction(**answer_for("דנה")), "x")
        assert not (await provider.extract(None)).text_upside_down


class TestSourcesAndNotes:
    def test_parses_a_source_with_and_without_the_raw_marker(self):
        assert parse_source("gemini:gemini-2.5-flash:raw") == Source("gemini", "gemini-2.5-flash", oriented=False, prompt=SAVED_PROMPT)
        assert parse_source("groq:qwen/qwen3.8-27b") == Source("groq", "qwen/qwen3.8-27b", oriented=True, prompt=SAVED_PROMPT)

    @pytest.mark.parametrize("bad", ["gemini", "gemini:", ":model", "a:b:c", "a:b:raw:x"])
    def test_rejects_a_malformed_source(self, bad):
        with pytest.raises(ValueError):
            parse_source(bad)

    def test_the_default_order_prefers_the_best_measured_model(self):
        assert [(s.provider, s.model) for s in DEFAULT_SOURCES][0] == ("gemini", "gemini-2.5-flash")
        assert not DEFAULT_SOURCES[0].oriented              # those answers were saved from unturned pages
        assert DEFAULT_SOURCES[1] == Source("gemini", "gemini-2.5-flash", oriented=True, prompt=SAVED_PROMPT)   # then the same model, turned first
        assert len(set(DEFAULT_SOURCES)) == len(DEFAULT_SOURCES)

    def test_flip_notes_are_read_from_the_file_and_a_missing_file_means_none(self, tmp_path):
        note = tmp_path / "orientation.json"
        note.write_text(json.dumps({"note": "x", "flip_after_turn": ["p1", "p2"]}), encoding="utf-8")
        assert load_flip_pages(note) == {"p1", "p2"}
        assert load_flip_pages(tmp_path / "missing.json") == set()

    def test_the_real_notes_file_lists_the_five_pages_that_need_a_flip(self):
        from app.evaluation import DATA
        assert load_flip_pages(DATA / "sample_orientation.json") == {"p1_14", "p1_22", "p1_23", "p2_14", "p2_15"}


def test_saved_answers_are_found_even_after_the_prompt_changed(tmp_path, monkeypatch):
    """The demo replays answers saved with an earlier prompt; changing the prompt must not empty the demo."""
    import app.evaluation as evaluation
    from app.services.demo_seed import DEFAULT_SOURCES, SAVED_PROMPT, choose_answer

    folder = tmp_path / f"gemini-gemini-2.5-flash-{SAVED_PROMPT}"
    folder.mkdir()
    (folder / "p1_01.json").write_text(RawExtraction().model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(evaluation, "prompt_id", lambda: "ffffff")      # the prompt has changed since

    found = choose_answer("p1_01", sideways=False, sources=DEFAULT_SOURCES, cache_root=tmp_path)
    assert found is not None and found[0].model == "gemini-2.5-flash"
