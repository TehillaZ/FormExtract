"""Closed sender list: map raw text read from a form to one canonical sender, or to nothing."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

SENDERS_FILE = Path(__file__).resolve().parent.parent / "data" / "senders.json"

# generic words that appear in many institution names and carry no identity
_STOP = ["המרכז הרפואי", "מרכז רפואי", "הקריה הרפואית", "בית החולים", "ביה\"ח", "בי\"ח", "ע\"ש",
         "האוניברסיטאי", "קופת חולים", "קופ\"ח", "שירותי בריאות", "medical center"]


@dataclass(frozen=True)
class SenderMatch:
    name: str
    category: str
    exact: bool  # True: an alias/name appears verbatim; False: fuzzy match only


def normalize(text: str) -> str:
    t = text.lower()
    t = re.sub(r"[\"'׳״`]", "", t)          # ignore quote / geresh variants: רמב"ם == רמבם
    for w in _STOP:
        t = t.replace(re.sub(r"[\"'׳״`]", "", w), " ")
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@lru_cache(maxsize=1)
def _index() -> list[tuple[str, str, str]]:
    data = json.loads(SENDERS_FILE.read_text(encoding="utf-8"))
    rows = []
    for s in data["senders"]:
        for key in [s["name"], *s["aliases"]]:
            k = normalize(key)
            if k:
                rows.append((k, s["name"], s["category"]))
    # longest keys first so "אסותא אשדוד" wins over a shorter key
    return sorted(rows, key=lambda r: len(r[0]), reverse=True)


def match_sender(raw: str | None, fuzzy_threshold: float = 0.85) -> SenderMatch | None:
    if not raw or not raw.strip():
        return None
    text = normalize(raw)
    padded = f" {text} "
    for key, name, cat in _index():
        if f" {key} " in padded:
            return SenderMatch(name, cat, exact=True)
    best = max(_index(), key=lambda r: SequenceMatcher(None, text, r[0]).ratio())
    if SequenceMatcher(None, text, best[0]).ratio() >= fuzzy_threshold:
        return SenderMatch(best[1], best[2], exact=False)
    return None


def all_senders() -> list[str]:
    """Canonical names of the closed list (for dropdowns)."""
    data = json.loads(SENDERS_FILE.read_text(encoding="utf-8"))
    return sorted(s["name"] for s in data["senders"])
