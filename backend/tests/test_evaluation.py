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
