from app.validation.israeli_id import id_checksum_ok, normalize_id


def test_normalize_pads_and_strips():
    assert normalize_id("12345678-2") == "123456782"
    assert normalize_id(" 2345 678 ") == "002345678"
    assert normalize_id("12") is None
    assert normalize_id(None) is None


def test_checksum():
    assert id_checksum_ok("123456782")
    assert id_checksum_ok("000000018")
    assert not id_checksum_ok("123456789")
    assert not id_checksum_ok("12345")
