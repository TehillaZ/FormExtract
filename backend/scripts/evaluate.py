"""Run a vision provider over sample pages and score against data/ground_truth_draft.jsonl.

  python scripts/evaluate.py --provider gemini --split dev
  python scripts/evaluate.py --provider gemini --split dev --cached-only     # no API calls
  python scripts/evaluate.py --provider groq --pages p1_01,p1_02 --model <model-id>

Per field: accuracy, % flagged, and errors that were NOT flagged (the key metric).
Model answers are cached per provider, model and prompt in data/eval_cache, so re-scoring costs no API calls
and changing the prompt starts a fresh cache.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.evaluation import DATA, FIELDS, FieldStats, format_report, load_split, load_truth, score_record  # noqa: E402
from app.pipeline.barcodes import decode_barcodes  # noqa: E402
from app.pipeline.extract import build_record  # noqa: E402
from app.schemas import RawExtraction  # noqa: E402
from app.vision import get_provider  # noqa: E402
from app.vision.prompt import SYSTEM_PROMPT, USER_PROMPT  # noqa: E402


async def run_page(provider, name: str, limit: asyncio.Semaphore, cache_dir: Path, force: bool):
    """Returns (raw extraction, barcodes, seconds spent calling the API; 0 for a cache hit)."""
    cache = cache_dir / f"{name}.json"
    img = cv2.imread(str(DATA / "pages" / f"{name}.png"))
    barcodes = [b.text for b in decode_barcodes(img)]
    if cache.exists() and not force:
        return RawExtraction.model_validate_json(cache.read_text(encoding="utf-8")), barcodes, 0.0
    async with limit:
        started = time.perf_counter()
        raw = await provider.extract(img)
        seconds = time.perf_counter() - started
    cache.write_text(raw.model_dump_json(indent=1), encoding="utf-8")
    return raw, barcodes, seconds


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", default=settings.vision_provider)
    ap.add_argument("--model")
    ap.add_argument("--pages", help="comma separated page ids")
    ap.add_argument("--split", choices=["dev", "test"], help="use data/split.json; run test only for final numbers")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--cached-only", action="store_true", help="score only pages already in the cache")
    ap.add_argument("--force", action="store_true", help="ignore the cache and call the API again")
    return ap.parse_args()


def choose_pages(args: argparse.Namespace, truth: dict, cache_dir: Path) -> list[str]:
    pages = args.pages.split(",") if args.pages else sorted(truth)
    if args.split:
        wanted = load_split(args.split)
        pages = [p for p in pages if p in wanted]
    if args.limit:
        pages = pages[: args.limit]
    if args.cached_only:
        pages = [p for p in pages if (cache_dir / f"{p}.json").exists()]
    return pages


async def main() -> None:
    args = parse_args()
    truth = load_truth()
    provider = get_provider(args.provider, args.model)
    prompt_id = hashlib.sha1((SYSTEM_PROMPT + USER_PROMPT).encode()).hexdigest()[:6]
    tag = f"{provider.name}-{getattr(provider, 'model', '')}-{prompt_id}".replace("/", "_")
    cache_dir = DATA / "eval_cache" / tag
    cache_dir.mkdir(parents=True, exist_ok=True)
    pages = choose_pages(args, truth, cache_dir)

    limit = asyncio.Semaphore(settings.max_concurrency)
    results = await asyncio.gather(*(run_page(provider, p, limit, cache_dir, args.force) for p in pages),
                                   return_exceptions=True)

    stats = {name: FieldStats() for name in FIELDS}
    failed: list[tuple[str, str]] = []
    call_seconds: list[float] = []
    for page, result in zip(pages, results, strict=True):
        if isinstance(result, Exception):
            failed.append((page, repr(result)[:120]))
            continue
        raw, barcodes, seconds = result
        if seconds:
            call_seconds.append(seconds)
        rec = build_record(raw, barcodes, provider=provider.name)
        for name, (correct, flagged) in score_record(rec, truth[page]).items():
            stats[name].add(correct, flagged)

    print(f"\nprovider={tag}  checksum_mode={settings.id_checksum_mode}  pages={len(pages) - len(failed)}/{len(pages)}")
    print(format_report(stats))
    if call_seconds:
        print(f"avg latency {sum(call_seconds) / len(call_seconds):.1f}s over {len(call_seconds)} calls")
    for page, error in failed:
        print("FAILED", page, error)


if __name__ == "__main__":
    asyncio.run(main())
