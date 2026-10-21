from app.evaluation import FieldStats, format_report, score_record
from app.pipeline.extract import build_record
from app.schemas import RawExtraction, RawValue as V

TRUTH = {"id_number": "0011223344", "central_numbers": ["939376"], "received_date": "2026-06-18",
         "sender": "כללית", "commitment_numbers": ["730578626"]}


def rec(**kw):
    return build_record(RawExtraction(**kw), ["939376", "730578626"])


def test_correct_and_verified_fields_score_correct_and_unflagged():
    r = rec(central_numbers=[V(value="939376", source="sticker")],
            commitment_numbers=[V(value="730578626", source="printed")],
            sender=V(value="כללית", highlighted=True))
    out = score_record(r, TRUTH)
    assert out["central_numbers"] == (True, False)
    assert out["commitment_numbers"] == (True, False)
    assert out["sender"] == (True, False)


def test_wrong_but_flagged_is_not_a_silent_error():
    r = rec(central_numbers=[V(value="939999", source="handwritten")])
    assert score_record(r, TRUTH)["central_numbers"] == (False, True)


def test_id_compares_ignoring_leading_zeros():
    r = rec(id_numbers=[V(value="11223344")])
    assert score_record(r, TRUTH)["id_number"][0] is True


def test_sender_expected_empty():
    r = rec()
    assert score_record(r, {**TRUTH, "sender": None})["sender"][0] is True
    assert score_record(r, TRUTH)["sender"][0] is False


def test_report_counts_silent_errors():
    s = FieldStats()
    s.add(True, False)
    s.add(False, False)   # wrong and unflagged
    s.add(False, True)    # wrong but flagged
    assert (s.silent_errors, s.errors) == (1, 2)
    assert "1/2" in format_report({"sender": s})


# ---- comparing two runs on the same pages ------------------------------------------------------------------

from app.evaluation import cache_tag, compare_paired, format_paired  # noqa: E402


def run(**pages):
    """run(p1={"sender": (True, False)}, ...) -> page -> field -> (correct, flagged)"""
    return pages


class TestComparePaired:
    def test_counts_who_was_right_where_and_the_four_groups_add_up(self):
        a = run(p1={"sender": (True, False)}, p2={"sender": (True, False)}, p3={"sender": (False, True)}, p4={"sender": (False, False)})
        b = run(p1={"sender": (True, False)}, p2={"sender": (False, False)}, p3={"sender": (True, False)}, p4={"sender": (False, True)})
        f = compare_paired(a, b)["sender"]
        assert (f.both_right, f.only_a, f.only_b, f.both_wrong) == (1, 1, 1, 1)
        assert f.both_right + f.only_a + f.only_b + f.both_wrong == f.pages == 4
        assert (f.correct_a, f.correct_b) == (2, 2)

    def test_counts_each_sides_errors_that_were_not_flagged(self):
        a = run(p1={"id_number": (False, False)}, p2={"id_number": (False, True)})     # one silent error, one flagged
        b = run(p1={"id_number": (False, False)}, p2={"id_number": (False, False)})    # two silent errors
        f = compare_paired(a, b)["id_number"]
        assert (f.silent_a, f.silent_b) == (1, 2)

    def test_only_pages_both_runs_scored_are_compared(self):
        a = run(p1={"sender": (True, False)}, p2={"sender": (True, False)}, p3={"sender": (True, False)})
        b = run(p2={"sender": (False, False)})
        f = compare_paired(a, b)["sender"]
        assert f.pages == 1 and (f.only_a, f.both_right) == (1, 0)    # a's other pages are not held against b

    def test_no_shared_pages_gives_nothing_to_compare(self):
        assert compare_paired(run(p1={"sender": (True, False)}), run(p2={"sender": (True, False)})) == {}

    def test_fields_come_out_in_the_usual_order(self):
        both = {"commitment_numbers": (True, False), "id_number": (True, False), "sender": (True, False)}
        assert list(compare_paired(run(p=both), run(p=both))) == ["id_number", "sender", "commitment_numbers"]

    def test_the_text_report_names_both_sides_and_the_page_count(self):
        both = run(p1={"sender": (True, False)})
        text = format_paired(compare_paired(both, both), "gemini:m", "groq:q")
        assert "1 pages scored by both" in text and "gemini:m" in text and "groq:q" in text


class TestCacheTag:
    def test_names_provider_model_and_prompt_and_marks_orientation(self):
        tag = cache_tag("groq", "qwen/qwen3.8-27b", oriented=True)
        assert tag.startswith("groq-qwen_qwen3.8-27b-") and tag.endswith("-oriented") and "/" not in tag
        assert not cache_tag("groq", "qwen/qwen3.8-27b", oriented=False).endswith("-oriented")

    def test_the_prompt_is_part_of_the_name_so_a_new_prompt_starts_a_fresh_cache(self, monkeypatch):
        import app.evaluation as ev
        before = cache_tag("gemini", "m", True)
        monkeypatch.setattr(ev, "SYSTEM_PROMPT", ev.SYSTEM_PROMPT + " changed")
        assert cache_tag("gemini", "m", True) != before
