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


# ---- recurring mistakes -------------------------------------------------------------------------

def test_a_correction_remembers_where_the_mistake_happened(s):
    r = repo.save_record(s, make(central="939376", sender="מכבי"))
    repo.patch_record(s, r.id, {"central_numbers": ["939999"]})
    with session_mod._factory() as fresh:
        row = fresh.query(repo.CorrectionRow).one()
    assert (row.field, row.sender, row.source, row.confidence) == ("central_numbers", "מכבי", "barcode", "high")   # a barcode match made it look certain


def test_summary_groups_repeated_mistakes_and_counts_unflagged_ones(s):
    for central in ("939001", "939002"):
        r = repo.save_record(s, make(central=central, sender="מכבי"))
        repo.patch_record(s, r.id, {"central_numbers": ["939999"]})
    r = repo.save_record(s, make(sender="כללית"))
    repo.patch_record(s, r.id, {"received_date": "20/06/2026"})
    groups = repo.correction_summary(s)
    assert [(g["field"], g["sender"], g["count"]) for g in groups] == [
        ("central_numbers", "מכבי", 2), ("received_date", "כללית", 1)]
    assert groups[0]["examples"] == [{"old": "939002", "new": "939999"}, {"old": "939001", "new": "939999"}]
    assert groups[0]["sources"] == {"barcode": 2} and groups[0]["unflagged"] == 2
    assert repo.correction_summary(s, min_count=2)[0]["count"] == 2 and len(repo.correction_summary(s, min_count=2)) == 1


def test_a_confirmation_is_not_a_mistake(s):
    r = repo.save_record(s, make())
    repo.patch_record(s, r.id, {"first_name": None})
    assert repo.correction_summary(s) == []


def test_columns_are_added_to_an_old_corrections_table(tmp_path):
    import sqlalchemy as sa
    url = f"sqlite:///{tmp_path / 'old.db'}"
    old = sa.create_engine(url)
    with old.begin() as c:
        c.execute(sa.text("CREATE TABLE corrections (id INTEGER PRIMARY KEY, record_id CHAR(32), field VARCHAR(40), "
                          "old_value TEXT, new_value TEXT, at DATETIME)"))
    old.dispose()
    cols = {c["name"] for c in sa.inspect(session_mod.init_db(url)).get_columns("corrections")}
    assert {"sender", "template", "source", "confidence"} <= cols


# ---- suggestions from earlier corrections ---------------------------------------------------------

def fix_times(s, n, *, sender="מכבי", central="939376", new="939999"):
    """n earlier forms from the sender, each with the same wrong central number, each corrected the same way."""
    for _ in range(n):
        r = repo.save_record(s, make(central=central, sender=sender))
        repo.patch_record(s, r.id, {"central_numbers": [new]})


def suggestion_for(s, **kw):
    return repo.get_record(s, repo.save_record(s, make(**kw)).id).suggestions


def test_after_enough_consistent_fixes_the_same_reading_gets_a_suggestion(s):
    fix_times(s, 3)
    [sg] = suggestion_for(s, central="939376", sender="מכבי")
    assert (sg.field, sg.current, sg.suggested, sg.times, sg.total, sg.sender) == (
        "central_numbers", "939376", "939999", 3, 3, "מכבי")
    assert len(sg.examples) == 3


def test_too_few_fixes_offer_nothing(s):
    fix_times(s, 2)
    assert suggestion_for(s, central="939376", sender="מכבי") == []


def test_another_sender_or_another_reading_is_not_affected(s):
    fix_times(s, 3)
    assert suggestion_for(s, central="939376", sender="כללית") == []
    assert suggestion_for(s, central="939377", sender="מכבי") == []


def test_fixes_that_disagree_offer_nothing(s):
    fix_times(s, 2, new="939999")
    fix_times(s, 2, new="939888")
    assert suggestion_for(s, central="939376", sender="מכבי") == []


def test_a_suggestion_is_never_applied_and_a_value_a_person_typed_has_none(s):
    fix_times(s, 3)
    r = repo.save_record(s, make(central="939376", sender="מכבי"))
    assert r.central_numbers[0].value == "939376"            # only offered
    assert repo.get_record(s, r.id).suggestions                 # still on offer after reading it again
    assert repo.patch_record(s, r.id, {"central_numbers": ["939111"]}).suggestions == []


def test_approved_records_get_no_suggestions(s):
    fix_times(s, 3)
    r = repo.save_record(s, make(central="939376", sender="מכבי"))
    assert repo.approve_record(s, r.id).suggestions == []


# ---- an empty sender, filled in the same way on forms of one type ---------------------------------------------

def form_without_sender(template="meuhedet_commitment", n=0):
    raw = RawExtraction(template=template, id_numbers=[V(value="011223344", source="printed")],
                        stamp_date=V(value="18/06/2026", source="stamp"),
                        commitment_numbers=[V(value=f"72000000{n}", source="printed")])
    return build_record(raw, [], provider="test")


def fill_in_sender(s, times, sender="מאוחדת", template="meuhedet_commitment"):
    for n in range(times):
        r = repo.save_record(s, form_without_sender(template, n))
        repo.patch_record(s, r.id, {"sender": sender})


def test_an_empty_sender_gets_the_sender_people_keep_filling_in_on_that_form_type(s):
    fill_in_sender(s, 3)
    new = repo.get_record(s, repo.save_record(s, form_without_sender(n=9)).id)
    [sg] = new.suggestions
    assert (sg.field, sg.current, sg.suggested, sg.times, sg.total) == ("sender", None, "מאוחדת", 3, 3)
    assert new.sender.value is None                          # only offered, never filled in


def test_an_empty_sender_is_not_suggested_from_another_form_type_or_from_too_few_fixes(s):
    fill_in_sender(s, 3, template="meuhedet_commitment")
    assert repo.get_record(s, repo.save_record(s, form_without_sender("clalit_form17", 9)).id).suggestions == []
    assert repo.get_record(s, repo.save_record(s, form_without_sender(None, 8)).id).suggestions == []   # type unknown
    s.query(repo.CorrectionRow).delete()
    s.commit()
    fill_in_sender(s, 2)
    assert repo.get_record(s, repo.save_record(s, form_without_sender(n=7)).id).suggestions == []


def test_fixes_that_fill_in_different_senders_make_no_suggestion(s):
    fill_in_sender(s, 2, sender="מאוחדת")
    fill_in_sender(s, 2, sender="מכבי")
    assert repo.get_record(s, repo.save_record(s, form_without_sender(n=9)).id).suggestions == []
