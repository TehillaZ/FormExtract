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



# ---- an ID is "verified" only when it is corroborated: passing the check digit alone is not enough --------------

class TestIdCorroboration:
    VALID = "011223344"     # passes the check digit

    def id_field(self, *reads: V):
        return build_record(RawExtraction(id_numbers=list(reads)), []).id_number

    def test_one_printed_read_nobody_highlighted_is_not_verified(self):
        # the printer's or a staff member's ID looks exactly like this, and about one random number in ten passes
        f = self.id_field(V(value=self.VALID, source="printed"))
        assert f.value == "011223344" and f.confidence == "medium" and f.reasons == ["קריאה אחת בלבד, ללא סימון"]

    def test_the_form_pointing_at_it_makes_it_verified(self):
        assert self.id_field(V(value=self.VALID, source="sticker", highlighted=True)).confidence == "high"

    def test_the_same_id_read_twice_makes_it_verified_even_without_a_highlight(self):
        f = self.id_field(V(value=self.VALID, source="sticker"), V(value="11223344", source="handwritten"))
        assert f.value == "011223344" and f.confidence == "high" and f.reasons == []

    def test_a_lone_handwritten_read_is_still_low(self):
        f = self.id_field(V(value=self.VALID, source="handwritten"))
        assert f.confidence == "low" and "כתב יד" in f.reasons

    def test_two_different_reads_are_low_even_if_both_pass(self):
        f = self.id_field(V(value="011223344", source="printed"), V(value="308462795", source="printed"))
        assert f.confidence == "low"

    def test_a_failed_check_digit_stays_low_however_much_agrees_or_is_highlighted(self):
        f = self.id_field(V(value="001122334", source="sticker", highlighted=True), V(value="001122334", source="handwritten"))
        assert f.confidence == "low" and "ספרת ביקורת לא תקינה" in f.reasons

    def test_corroboration_must_support_the_chosen_value_not_a_rival(self):
        # a highlighted read of one ID and a lone printed read of another: only the highlighted one is chosen
        f = self.id_field(V(value="308462795", source="printed"), V(value=self.VALID, source="sticker", highlighted=True))
        assert f.value == "011223344" and f.confidence == "high"

    def test_lenient_mode_is_unchanged_the_check_digit_never_makes_it_high(self, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "id_checksum_mode", "lenient")
        f = self.id_field(V(value=self.VALID, source="sticker", highlighted=True))
        assert f.confidence == "medium" and f.reasons == []
