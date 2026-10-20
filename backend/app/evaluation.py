"""Scoring of extracted records against the ground truth (PLAN 10).

For each field: was it correct, and was it flagged (confidence below high)? The metric that matters most is
the errors that were NOT flagged, because those reach the database unnoticed.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.schemas import CommitmentRecord
from app.validation.senders import match_sender

DATA = Path(__file__).resolve().parents[2] / "data"
REPORTS_DIR = DATA / "eval_reports"
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


# ---- saved reports: what the accuracy screen shows ----------------------------------------------

class FieldResult(BaseModel):
    pages: int
    correct: int
    flagged: int
    silent_errors: int      # wrong and not flagged: the errors that reach the database unnoticed


class EvaluationReport(BaseModel):
    """The outcome of one evaluation run, small enough to keep in git and to show in the UI."""
    tag: str                                  # provider-model-prompt[-oriented]
    provider: str
    model: str
    prompt_id: str
    oriented: bool                            # whether orientation correction was part of the run
    checksum_mode: str
    split: Literal["dev", "test", "all"]
    created_at: datetime
    pages_scored: int
    pages_failed: int = 0
    fields: dict[str, FieldResult]


def build_report(*, tag: str, provider: str, model: str, prompt_id: str, oriented: bool, checksum_mode: str,
                 split: str, pages_scored: int, pages_failed: int, stats: dict[str, FieldStats]) -> EvaluationReport:
    return EvaluationReport(
        tag=tag, provider=provider, model=model, prompt_id=prompt_id, oriented=oriented, checksum_mode=checksum_mode,
        split=split, created_at=datetime.now(UTC).replace(microsecond=0), pages_scored=pages_scored,
        pages_failed=pages_failed,
        fields={name: FieldResult(pages=s.pages, correct=s.correct, flagged=s.flagged, silent_errors=s.silent_errors)
                for name, s in stats.items()})


def save_report(report: EvaluationReport, directory: Path = REPORTS_DIR) -> Path:
    """One file per run configuration and split; running it again replaces the earlier result."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{report.tag}__{report.split}.json"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_reports(directory: Path = REPORTS_DIR) -> list[EvaluationReport]:
    """Every readable report, newest first. A file that is not a valid report is skipped, not fatal."""
    reports = []
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        try:
            reports.append(EvaluationReport.model_validate_json(path.read_text(encoding="utf-8")))
        except (ValidationError, OSError, ValueError):
            continue
    return sorted(reports, key=lambda r: r.created_at, reverse=True)


@dataclass(frozen=True)
class Coverage:
    pages: int      # pages with a verified answer
    dev: int
    test: int       # the held-out pages that must not be tuned on


@dataclass(frozen=True)
class EvaluationStore:
    """Where the accuracy screen gets its data. Tests and the browser-test server point it elsewhere."""
    reports_dir: Path = REPORTS_DIR
    truth_file: Path = DATA / "ground_truth_draft.jsonl"
    split_file: Path = DATA / "split.json"

    def reports(self) -> list[EvaluationReport]:
        return load_reports(self.reports_dir)

    def coverage(self) -> Coverage:
        if not self.truth_file.is_file():
            return Coverage(0, 0, 0)
        pages = len(load_truth(self.truth_file))
        if not self.split_file.is_file():
            return Coverage(pages, pages, 0)
        split = json.loads(self.split_file.read_text(encoding="utf-8"))
        return Coverage(pages, len(split.get("dev", [])), len(split.get("test", [])))
