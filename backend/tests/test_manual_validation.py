from datetime import date

import pytest

from app.validation.dates import normalize_date
from app.validation.manual import InvalidValue, clean_list, clean_scalar
from app.validation.numbers import CENTRAL, COMMITMENT


def test_central_rule():
    assert CENTRAL.clean("93 93-76") == "939376"
    assert CENTRAL.is_valid("939376") and not CENTRAL.is_valid("9393")


def test_commitment_rule():
    assert COMMITMENT.clean(" X132 767 ") == "X132767"
    assert COMMITMENT.is_valid("X132767") and COMMITMENT.is_valid("03240")
    assert not COMMITMENT.is_valid("123") and not COMMITMENT.is_valid("1234567890123")


def test_clean_list_drops_blanks_and_duplicates_but_rejects_garbage():
    assert clean_list("central_numbers", ["939376", " ", None, "939376"]) == ["939376"]
    with pytest.raises(InvalidValue):
        clean_list("central_numbers", ["abc"])   # typed garbage is an error, not silently dropped


def test_clean_scalar():
    assert clean_scalar("id_number", "1122344") == "001122344"
    assert clean_scalar("received_date", "2026-06-18") == "2026-06-18"
    assert clean_scalar("received_date", "18.6.26") == "2026-06-18"
    assert clean_scalar("first_name", "  דנה ") == "דנה"
    assert clean_scalar("first_name", "   ") is None
    with pytest.raises(InvalidValue):
        clean_scalar("received_date", "31/02/2026")


def test_normalize_date_accepts_iso_and_rejects_invalid_iso():
    assert normalize_date("2026-06-18") == date(2026, 6, 18)
    assert normalize_date("2026-13-45") is None
