import json
from pathlib import Path

import pytest

from app.validation.senders import match_sender

GT = Path(__file__).resolve().parents[2] / "data" / "ground_truth_draft.jsonl"


@pytest.mark.parametrize("raw,expected", [
    ("רמב\"ם", "רמב\"ם - הקריה הרפואית לבריאות האדם"),
    ("רמבם", "רמב\"ם - הקריה הרפואית לבריאות האדם"),
    ("קופ\"ח מאוחדת", "מאוחדת"),
    ("המרכז הרפואי תל אביב ע\"ש סוראסקי", "המרכז הרפואי תל אביב ע\"ש סוראסקי (איכילוב)"),
    ("בית החולים הציבורי אסותא אשדוד", "בית החולים האוניברסיטאי אסותא אשדוד"),
    ("ברזלי", "מרכז רפואי ברזילי"),  # typo -> fuzzy
])
def test_known_spellings(raw, expected):
    m = match_sender(raw)
    assert m is not None and m.name == expected


@pytest.mark.parametrize("raw", ["", None, "מעבדה וירולוגית", "בית ג'אן"])
def test_unknown_stays_empty(raw):
    assert match_sender(raw) is None


@pytest.mark.skipif(not GT.exists(), reason="ground truth is local data, not in git")
def test_every_ground_truth_sender_maps():
    rows = [json.loads(line) for line in GT.read_text(encoding="utf-8").splitlines() if line.strip()]
    missing = sorted({r["sender"] for r in rows if match_sender(r["sender"]) is None})
    assert missing == []
