from datetime import date

from app.pipeline.extract import build_record
from app.validation.dates import normalize_date
from app.schemas import RawExtraction, RawValue as V


def test_normalize_date():
    assert normalize_date("18/06/2026") == date(2026, 6, 18)
    assert normalize_date("8.6.26") == date(2026, 6, 8)
    assert normalize_date("32/13/2026") is None
    assert normalize_date(None) is None


def test_missing_fields_are_flagged_not_guessed():
    rec = build_record(RawExtraction(), [])
    for f in (rec.first_name, rec.id_number, rec.received_date, rec.sender,
              rec.central_numbers[0], rec.commitment_numbers[0]):
        assert f.value is None and f.confidence == "low" and f.reasons == ["לא נמצא"]


def test_barcode_verifies_central_and_commitment():
    raw = RawExtraction(central_numbers=[V(value="939376", source="sticker")],
                        commitment_numbers=[V(value="730578626", source="printed")])
    rec = build_record(raw, ["939376", "730578626 "])
    assert rec.central_numbers[0].confidence == "high"
    assert rec.commitment_numbers[0].confidence == "high"


def test_handwritten_central_unverified_is_low():
    rec = build_record(RawExtraction(central_numbers=[V(value="939158", source="handwritten")]), [])
    assert rec.central_numbers[0].confidence == "low"


def test_central_wrong_length_is_low():
    rec = build_record(RawExtraction(central_numbers=[V(value="9391", source="sticker")]), [])
    assert rec.central_numbers[0].confidence == "low"


def test_stamp_vs_handwritten_conflict_picks_stamp_and_flags():
    raw = RawExtraction(stamp_date=V(value="18/06/2026"), handwritten_date=V(value="19/06/2026"))
    f = build_record(raw, []).received_date
    assert f.value == "2026-06-18" and f.confidence == "low"


def test_stamp_matching_handwritten_is_high():
    raw = RawExtraction(stamp_date=V(value="18/06/2026"), handwritten_date=V(value="18.6.26"))
    assert build_record(raw, []).received_date.confidence == "high"


def test_unknown_sender_stays_empty_with_raw_text():
    f = build_record(RawExtraction(sender=V(value="קליניקה לא ידועה")), []).sender
    assert f.value is None and f.raw_text == "קליניקה לא ידועה" and f.confidence == "low"


def test_inconsistent_ids_flagged():
    raw = RawExtraction(id_numbers=[V(value="001122334"), V(value="001122335")])
    assert build_record(raw, []).id_number.confidence == "low"


def test_unreadable_image_marks_everything_low():
    raw = RawExtraction(image_unreadable=True, sender=V(value="כללית"))
    assert build_record(raw, []).sender.confidence == "low"


def test_highlighted_id_wins_over_printed_distractor():
    raw = RawExtraction(id_numbers=[V(value="308462795", source="printed"),
                                    V(value="01122334", source="handwritten", highlighted=True)])
    assert build_record(raw, []).id_number.value == "001122334"


def test_sender_with_rival_entity_is_capped_at_medium():
    raw = RawExtraction(sender=V(value="כללית"), other_senders=[V(value="רמב\"ם")])
    f = build_record(raw, []).sender
    assert f.value == "כללית" and f.confidence == "medium"


def test_highlighted_sender_stays_high():
    raw = RawExtraction(sender=V(value="כללית", highlighted=True), other_senders=[V(value="רמב\"ם")])
    assert build_record(raw, []).sender.confidence == "high"


def test_central_number_not_repeated_as_commitment():
    raw = RawExtraction(central_numbers=[V(value="939135", source="handwritten")],
                        commitment_numbers=[V(value="939135"), V(value="000302651707", source="printed")])
    rec = build_record(raw, [])
    assert [f.value for f in rec.commitment_numbers] == ["000302651707"]


def test_barcode_match_does_not_beat_highlight():
    raw = RawExtraction(commitment_numbers=[V(value="0046025783", source="printed"),
                                            V(value="730578626", source="printed", highlighted=True)])
    rec = build_record(raw, ["0046025783", "730578626"])
    assert [(f.value, f.confidence) for f in rec.commitment_numbers] == [("730578626", "high")]


def test_barcode_match_among_unmarked_competitors_is_medium():
    raw = RawExtraction(commitment_numbers=[V(value="0046025783", source="printed"),
                                            V(value="730578626", source="printed")])
    rec = build_record(raw, ["0046025783", "730578626"])
    assert {f.confidence for f in rec.commitment_numbers} == {"medium"}
