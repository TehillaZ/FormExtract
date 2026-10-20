"""Scoring of extracted records against the ground truth (PLAN 10).

For each field: was it correct, and was it flagged (confidence below high)? The metric that matters most is
the errors that were NOT flagged, because those reach the database unnoticed.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from app.schemas import CommitmentRecord
from app.validation.senders import match_sender

DATA = Path(__file__).resolve().parents[2] / "data"
FIELDS = ("id_number", "central_numbers", "received_date", "sender", "commitment_numbers")

Outcome = tuple[bool, bool]   # (correct, flagged)


def load_truth(path: Path = DATA / "ground_truth_draft.jsonl") -> dict[str, dict]:
    rows = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return {r["page"]: r for r in rows}


def load_split(name: str) -> set[str]:
    return set(json.loads((DATA / "split.json").read_text(encoding="utf-8"))[name])


def _id_key(value: str | None) -> str | None:
    """IDs compare ignoring leading zeros: the ground truth keeps the digits as written (8 or 10 digits too)."""
    return (value or "").lstrip("0") or None


def _as_set(values: Iterable[str | None] | None) -> frozenset[str]:
    return frozenset(str(v).strip() for v in (values or []) if v)


def _sender_correct(got: str | None, want: str | None) -> bool:
    if not want:
        return not got                       # nothing expected: an empty sender is right
    if not got:
        return False
    canonical = match_sender(want)
    return got == (canonical.name if canonical else want)


def score_record(rec: CommitmentRecord, truth: dict) -> dict[str, Outcome]:
    def flagged(*fields) -> bool:
        return any(f.confidence != "high" for f in fields)

    return {
        "id_number": (_id_key(rec.id_number.value) == _id_key(truth.get("id_number")), flagged(rec.id_number)),
        "central_numbers": (_as_set(f.value for f in rec.central_numbers) == _as_set(truth.get("central_numbers")),
                            flagged(*rec.central_numbers)),
        "received_date": (rec.received_date.value == truth.get("received_date"), flagged(rec.received_date)),
        "sender": (_sender_correct(rec.sender.value, truth.get("sender")), flagged(rec.sender)),
        "commitment_numbers": (_as_set(f.value for f in rec.commitment_numbers) == _as_set(truth.get("commitment_numbers")),
                               flagged(*rec.commitment_numbers)),
    }


@dataclass
class FieldStats:
    pages: int = 0
    correct: int = 0
    flagged: int = 0
    silent_errors: int = 0     # wrong and not flagged

    def add(self, correct: bool, flagged: bool) -> None:
        self.pages += 1
        self.correct += correct
        self.flagged += flagged
        self.silent_errors += (not correct) and (not flagged)

    @property
    def errors(self) -> int:
        return self.pages - self.correct


def format_report(stats: dict[str, FieldStats]) -> str:
    lines = [f"{'field':<20}{'accuracy':>10}{'flagged':>10}{'silent errors':>16}"]
    for name, s in stats.items():
        n = s.pages or 1
        lines.append(f"{name:<20}{s.correct / n:>10.0%}{s.flagged / n:>10.0%}{f'{s.silent_errors}/{s.errors}':>16}")
    return "\n".join(lines)
