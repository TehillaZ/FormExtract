import os
from datetime import date

import pytest

import app.db.session as session_mod
from app.db import repo
from app.db.models import Base
from app.pipeline.extract import build_record
from app.schemas import RawExtraction, RawValue as V


@pytest.fixture()
def s():
    """In-memory SQLite by default; set TEST_DATABASE_URL to run the same tests on PostgreSQL."""
    url = os.environ.get("TEST_DATABASE_URL", "sqlite://")
    if not url.startswith("sqlite") and not url.rsplit("/", 1)[-1].endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must name a database ending in _test: these tests drop every table")
    engine = session_mod.init_db(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with session_mod._factory() as sess:
        yield sess


def make(commitment="730578626", central="939376", sender="כללית", d="18/06/2026"):
    raw = RawExtraction(
        sender=V(value=sender, highlighted=True), stamp_date=V(value=d, source="stamp"),
        id_numbers=[V(value="011223344", source="printed")],
        central_numbers=[V(value=central, source="sticker")] if central else [],
        commitment_numbers=[V(value=commitment, source="printed")] if commitment else [])
    return build_record(raw, [central or "", commitment or ""])


def test_save_and_get_roundtrip(s):
    saved = repo.save_record(s, make())
    got = repo.get_record(s, saved.id)
    assert got.commitment_numbers[0].value == "730578626"
    assert got.status == "pending" and got.received_date.value == "2026-06-18"


def test_records_without_commitment_number_can_coexist_and_approve(s):
    a = repo.save_record(s, make(commitment=None, central="939111"))
    b = repo.save_record(s, make(commitment=None, central="939222"))
    repo.approve_record(s, a.id)
    assert repo.approve_record(s, b.id).status == "approved"   # empty never counts as duplicate


def test_duplicate_pending_is_a_warning_not_a_block(s):
    repo.save_record(s, make())
    b = repo.save_record(s, make())
    assert any("730578626" in w for w in b.duplicate_warnings)


def test_second_approval_of_same_commitment_number_is_rejected(s):
    a = repo.save_record(s, make())
    b = repo.save_record(s, make())
    repo.approve_record(s, a.id)
    with pytest.raises(repo.DuplicateCommitmentError) as e:
        repo.approve_record(s, b.id)
    assert e.value.numbers == ["730578626"]
    assert repo.get_record(s, b.id).status == "pending"


def test_patch_logs_correction_and_marks_manual(s):
    r = repo.save_record(s, make(central="939376"))
    out = repo.patch_record(s, r.id, {"central_numbers": ["939999"], "received_date": "20/06/2026"})
    assert out.central_numbers[0].value == "939999" and out.central_numbers[0].source == "manual"
    assert out.received_date.value == "2026-06-20" and out.received_date.confidence == "high"
    assert {(c.field, c.old_value, c.new_value) for c in out.corrections} == {
        ("central_numbers", "939376", "939999"), ("received_date", "2026-06-18", "2026-06-20")}


def test_patch_validates(s):
    r = repo.save_record(s, make())
    with pytest.raises(repo.InvalidValue):
        repo.patch_record(s, r.id, {"sender": "גוף לא קיים"})
    with pytest.raises(repo.InvalidValue):
        repo.patch_record(s, r.id, {"central_numbers": ["123"]})
    with pytest.raises(repo.InvalidValue):
        repo.patch_record(s, r.id, {"received_date": "01/01/2999"})


def test_editing_approved_record_returns_it_to_pending(s):
    r = repo.save_record(s, make())
    repo.approve_record(s, r.id)
    assert repo.patch_record(s, r.id, {"first_name": "דנה"}).status == "pending"


def test_search_and_filters(s):
    repo.save_record(s, make(commitment="111111111", central="939001", sender="כללית"))
    repo.save_record(s, make(commitment="222222222", central="939002", sender="מכבי", d="01/07/2026"))
    assert len(repo.list_records(s)) == 2
    assert [r.sender.value for r in repo.list_records(s, q="939002")] == ["מכבי"]
    assert [r.sender.value for r in repo.list_records(s, q="111111")] == ["כללית"]
    assert len(repo.list_records(s, sender="מכבי")) == 1
    assert len(repo.list_records(s, date_from=date(2026, 7, 1))) == 1
    assert len(repo.list_records(s, status="approved")) == 0


def test_listing_many_records_uses_a_constant_number_of_queries(s):
    import sqlalchemy as sa
    for i in range(25):
        repo.save_record(s, make(commitment=f"7305{i:05d}", central=f"93{i:04d}"))
    count = 0

    def tick(*_):
        nonlocal count
        count += 1

    engine = s.get_bind()
    sa.event.listen(engine, "before_cursor_execute", tick)
    try:
        assert len(repo.list_records(s)) == 25
    finally:
        sa.event.remove(engine, "before_cursor_execute", tick)
    assert count <= 8   # main query + 3 eager loads + 2 duplicate lookups; was ~5 per record


# ---- confirming: saving a flagged field unchanged means "I checked, it is right" ----------------

def test_saving_a_flagged_field_unchanged_confirms_it_without_a_log_entry(s):
    r = repo.save_record(s, make())
    assert r.received_date.confidence == "medium"            # a stamp alone is not verified
    out = repo.patch_record(s, r.id, {"received_date": "18/06/2026"})
    assert out.received_date.value == "2026-06-18"
    assert (out.received_date.confidence, out.received_date.source) == ("high", "manual")
    assert out.received_date.reasons == ["אושר ידנית"]
    assert out.corrections == []                              # nothing was corrected


def test_saving_empty_for_a_missing_field_confirms_it_is_empty(s):
    r = repo.save_record(s, make(commitment=None))
    assert r.commitment_numbers[0].value is None and r.commitment_numbers[0].confidence == "low"
    out = repo.patch_record(s, r.id, {"commitment_numbers": []})
    only = out.commitment_numbers[0]
    assert (only.value, only.confidence, only.reasons) == (None, "high", ["אושר ידנית: אין בטופס"])
    assert out.corrections == []


def test_saving_a_verified_field_unchanged_changes_nothing(s):
    r = repo.save_record(s, make())
    assert r.sender.confidence == "high"
    out = repo.patch_record(s, r.id, {"sender": "כללית"})
    assert (out.sender.confidence, out.sender.source) == (r.sender.confidence, r.sender.source)   # not marked manual
    assert out.corrections == []


def test_clearing_a_value_is_a_logged_correction_and_leaves_a_confirmed_empty_field(s):
    r = repo.save_record(s, make(central="939376"))
    out = repo.patch_record(s, r.id, {"central_numbers": []})
    assert (out.central_numbers[0].value, out.central_numbers[0].confidence) == (None, "high")
    assert [(c.field, c.old_value, c.new_value) for c in out.corrections] == [("central_numbers", "939376", None)]


def test_a_confirmation_does_not_send_an_approved_record_back_to_pending(s):
    r = repo.save_record(s, make())
    repo.approve_record(s, r.id)
    assert repo.patch_record(s, r.id, {"first_name": ""}).status == "approved"
    assert repo.patch_record(s, r.id, {"first_name": "דנה"}).status == "pending"    # a real edit does


def test_confirming_every_flagged_field_makes_the_record_clean(s):
    r = repo.save_record(s, make())
    assert r.needs_review()
    # the ID is flagged too: one printed read that nobody highlighted is not enough to call it verified
    out = repo.patch_record(s, r.id, {"first_name": "", "last_name": "", "received_date": "18/06/2026", "id_number": "011223344"})
    assert not out.needs_review()
    approved, skipped = repo.approve_clean(s)
    assert approved == [r.id] and skipped == []


# ---- search by name and counting (these use database-specific JSON queries: run them on PostgreSQL too) ----

def named(first, last, commitment):
    raw = RawExtraction(first_name=V(value=first, source="printed"), last_name=V(value=last, source="printed"),
                        commitment_numbers=[V(value=commitment, source="printed")])
    return build_record(raw, [])


def test_search_finds_people_by_first_or_last_name_or_part_of_one(s):
    repo.save_record(s, named("רונן", "פלג", "111111111"))
    repo.save_record(s, named("דנה", "כהן", "222222222"))
    assert [r.last_name.value for r in repo.list_records(s, q="פלג")] == ["פלג"]
    assert [r.first_name.value for r in repo.list_records(s, q="דנ")] == ["דנה"]
    assert len(repo.list_records(s, q="zzz")) == 0


def test_count_ignores_paging_and_follows_the_filters(s):
    for i in range(5):
        repo.save_record(s, named("דנה", "כהן", f"30000000{i}"))
    approved = repo.save_record(s, named("רונן", "פלג", "400000000"))
    repo.approve_record(s, approved.id)
    assert repo.count_records(s) == 6
    assert len(repo.list_records(s, limit=2)) == 2 and repo.count_records(s) == 6
    assert repo.count_records(s, status="approved") == 1
    assert repo.count_records(s, q="דנה") == 5
    assert repo.count_records(s, q="דנה", status="approved") == 0
