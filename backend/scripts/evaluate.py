"""Run a vision provider over sample pages and score against data/ground_truth_draft.jsonl.

  python scripts/evaluate.py --provider gemini --pages p1_01,p1_02,p1_03
  python scripts/evaluate.py --provider groq --limit 10 --model <model-id>

Per field: accuracy, % flagged (confidence != high), % of errors that were NOT flagged (the key metric).
Results are cached per provider/model in data/eval_cache so reruns of scoring cost no API calls.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.pipeline.barcodes import decode_barcodes  # noqa: E402
from app.pipeline.extract import all_fields, build_record  # noqa: E402
from app.schemas import RawExtraction  # noqa: E402
from app.validation.israeli_id import normalize_id  # noqa: E402
from app.vision import get_provider  # noqa: E402
from app.vision.prompt import SYSTEM_PROMPT, USER_PROMPT  # noqa: E402

DATA = Path(__file__).resolve().parents[2] / "data"
FIELDS = ["id_number", "central_numbers", "received_date", "sender", "commitment_numbers"]


def load_truth() -> dict[str, dict]:
    rows = [json.loads(line) for line in (DATA / "ground_truth_draft.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    return {r["page"]: r for r in rows}


def _id_key(v: str | None) -> str | None:
    """Compare IDs ignoring leading zeros: ground truth keeps the digits as written (8 or 10 digits too)."""
    d = (v or "").lstrip("0")
    return d or None


def _norm_list(vals) -> frozenset[str]:
    return frozenset(str(v).strip() for v in (vals or []) if v)


def compare(rec, truth: dict) -> dict[str, tuple[bool, bool]]:
    """field -> (correct, flagged)."""
    out = {}
    out["id_number"] = (_id_key(rec.id_number.value) == _id_key(truth.get("id_number")), rec.id_number.confidence != "high")
    for name, fields in (("central_numbers", rec.central_numbers), ("commitment_numbers", rec.commitment_numbers)):
        got = _norm_list(f.value for f in fields)
        out[name] = (got == _norm_list(truth.get(name)), any(f.confidence != "high" for f in fields))
    out["received_date"] = (rec.received_date.value == truth.get("received_date"), rec.received_date.confidence != "high")
    out["sender"] = ((rec.sender.value or "") == "" and not truth.get("sender") or _sender_ok(rec.sender.value, truth.get("sender")),
                     rec.sender.confidence != "high")
    return out


def _sender_ok(got: str | None, want: str | None) -> bool:
    from app.validation.senders import match_sender
    if not got or not want:
        return False
    m = match_sender(want)
    return got == (m.name if m else want)


async def run_page(provider, name: str, sem: asyncio.Semaphore, cache_dir: Path, force: bool) -> tuple[RawExtraction, list[str], float]:
    cache = cache_dir / f"{name}.json"
    img = cv2.imread(str(DATA / "pages" / f"{name}.png"))
    barcodes = [b.text for b in decode_barcodes(img)]
    if cache.exists() and not force:
        return RawExtraction.model_validate_json(cache.read_text(encoding="utf-8")), barcodes, 0.0
    async with sem:
        t0 = time.perf_counter()
        raw = await provider.extract(img)
        dt = time.perf_counter() - t0
    cache.write_text(raw.model_dump_json(indent=1), encoding="utf-8")
    return raw, barcodes, dt


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=settings.vision_provider)
    ap.add_argument("--model")
    ap.add_argument("--pages", help="comma separated page ids")
    ap.add_argument("--split", choices=["dev", "test"], help="use data/split.json; run test only for final numbers")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--cached-only", action="store_true", help="score only pages already in the cache")
    ap.add_argument("--force", action="store_true", help="ignore cache and call the API again")
    args = ap.parse_args()

    truth = load_truth()
    pages = args.pages.split(",") if args.pages else sorted(truth)
    if args.split:
        pages = [p for p in pages if p in json.loads((DATA / "split.json").read_text())[args.split]]
    if args.limit:
        pages = pages[: args.limit]
    provider = get_provider(args.provider, args.model)
    prompt_id = hashlib.sha1((SYSTEM_PROMPT + USER_PROMPT).encode()).hexdigest()[:6]  # new prompt -> fresh cache
    tag = f"{provider.name}-{getattr(provider, 'model', '')}-{prompt_id}".replace("/", "_")
    cache_dir = DATA / "eval_cache" / tag
    cache_dir.mkdir(parents=True, exist_ok=True)
    if args.cached_only:
        pages = [p for p in pages if (cache_dir / f"{p}.json").exists()]
    sem = asyncio.Semaphore(settings.max_concurrency)

    results = await asyncio.gather(*(run_page(provider, p, sem, cache_dir, args.force) for p in pages), return_exceptions=True)

    stats = {f: {"n": 0, "ok": 0, "flagged": 0, "silent_err": 0} for f in FIELDS}
    failed, times = [], []
    for page, res in zip(pages, results):
        if isinstance(res, Exception):
            failed.append((page, repr(res)[:120]))
            continue
        raw, barcodes, dt = res
        if dt:
            times.append(dt)
        rec = build_record(raw, barcodes, provider=provider.name)
        for f, (ok, flagged) in compare(rec, truth[page]).items():
            s = stats[f]
            s["n"] += 1
            s["ok"] += ok
            s["flagged"] += flagged
            s["silent_err"] += (not ok) and (not flagged)

    print(f"\nprovider={tag}  checksum_mode={settings.id_checksum_mode}  pages={len(pages) - len(failed)}/{len(pages)}")
    print(f"{'field':<20}{'accuracy':>10}{'flagged':>10}{'silent errors':>16}")
    for f, s in stats.items():
        n = s["n"] or 1
        errs = s["n"] - s["ok"]
        silent = f"{s['silent_err']}/{errs}" if errs else "0/0"
        print(f"{f:<20}{s['ok'] / n:>10.0%}{s['flagged'] / n:>10.0%}{silent:>16}")
    if times:
        print(f"avg latency {sum(times) / len(times):.1f}s over {len(times)} calls")
    for p, e in failed:
        print("FAILED", p, e)


if __name__ == "__main__":
    asyncio.run(main())
