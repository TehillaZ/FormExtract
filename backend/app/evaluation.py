"""Scoring of extracted records against the ground truth (PLAN 10).

For each field: was it correct, and was it flagged (confidence below high)? The metric that matters most is
the errors that were NOT flagged, because those reach the database unnoticed.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.schemas import CommitmentRecord
from app.validation.senders import match_sender
from app.vision.prompt import SYSTEM_PROMPT, USER_PROMPT

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
    pages: list[str] = []                     # which pages were scored; empty in reports written before this existed
    fields: dict[str, FieldResult]


def build_report(*, tag: str, provider: str, model: str, prompt_id: str, oriented: bool, checksum_mode: str,
                 split: str, pages_scored: int, pages_failed: int, stats: dict[str, FieldStats],
                 pages: list[str] | None = None) -> EvaluationReport:
    return EvaluationReport(
        tag=tag, provider=provider, model=model, prompt_id=prompt_id, oriented=oriented, checksum_mode=checksum_mode,
        split=split, created_at=datetime.now(UTC).replace(microsecond=0), pages_scored=pages_scored,
        pages_failed=pages_failed, pages=sorted(pages or []),
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


# ---- cache names: which model, which prompt, with or without orientation correction -------------------------

def prompt_id() -> str:
    """A short fingerprint of the extraction prompt: a new prompt starts a fresh cache."""
    return hashlib.sha1((SYSTEM_PROMPT + USER_PROMPT).encode()).hexdigest()[:6]


def cache_tag(provider: str, model: str, oriented: bool) -> str:
    """The name of a run's cache folder and report: provider-model-prompt, plus -oriented when the page is turned first."""
    tag = f"{provider}-{model}-{prompt_id()}".replace("/", "_")
    return tag + "-oriented" if oriented else tag


# ---- the same pages, two models ------------------------------------------------------------------------------

@dataclass(frozen=True)
class PairedField:
    """One field, over the pages both runs scored: who was right where. The four counts add up to `pages`."""
    pages: int
    both_right: int
    only_a: int
    only_b: int
    both_wrong: int
    silent_a: int       # wrong and not flagged, in run A
    silent_b: int

    @property
    def correct_a(self) -> int:
        return self.both_right + self.only_a

    @property
    def correct_b(self) -> int:
        return self.both_right + self.only_b


def compare_paired(a: dict[str, dict[str, Outcome]], b: dict[str, dict[str, Outcome]]) -> dict[str, PairedField]:
    """Compare two runs page by page. `a` and `b` map page -> field -> (correct, flagged); only pages both
    scored count, so a model that scored fewer pages is never compared against pages it did not see."""
    shared = sorted(set(a) & set(b))
    fields = sorted({f for page in shared for f in a[page]} & {f for page in shared for f in b[page]},
                    key=lambda f: FIELDS.index(f) if f in FIELDS else len(FIELDS))
    out: dict[str, PairedField] = {}
    for field in fields:
        ok_a = [a[p][field][0] for p in shared]
        ok_b = [b[p][field][0] for p in shared]
        out[field] = PairedField(
            pages=len(shared),
            both_right=sum(x and y for x, y in zip(ok_a, ok_b, strict=True)),
            only_a=sum(x and not y for x, y in zip(ok_a, ok_b, strict=True)),
            only_b=sum(y and not x for x, y in zip(ok_a, ok_b, strict=True)),
            both_wrong=sum(not x and not y for x, y in zip(ok_a, ok_b, strict=True)),
            silent_a=sum(not a[p][field][0] and not a[p][field][1] for p in shared),
            silent_b=sum(not b[p][field][0] and not b[p][field][1] for p in shared))
    return out


def format_paired(paired: dict[str, PairedField], name_a: str, name_b: str) -> str:
    pages = next(iter(paired.values())).pages if paired else 0
    head = f"{'field':<20}{name_a[:18]:>20}{name_b[:18]:>20}{'both':>6}{'only A':>8}{'only B':>8}{'neither':>9}   silent A/B"
    lines = [f"{pages} pages scored by both", head]
    for field, p in paired.items():
        acc_a, acc_b = f"{p.correct_a}/{p.pages} ({p.correct_a / p.pages:.0%})", f"{p.correct_b}/{p.pages} ({p.correct_b / p.pages:.0%})"
        lines.append(f"{field:<20}{acc_a:>20}{acc_b:>20}{p.both_right:>6}{p.only_a:>8}{p.only_b:>8}{p.both_wrong:>9}   {p.silent_a} / {p.silent_b}")
    return "\n".join(lines)
