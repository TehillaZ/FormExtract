"""Fill the database with the sample forms from saved model answers, without calling any model.

  python scripts/seed_demo.py --dry-run          # what would be seeded, from which saved answer
  python scripts/seed_demo.py                    # seed every sample page that has a saved answer
  python scripts/seed_demo.py --pages p1_01,p1_03 --limit 5

Safe to repeat: a page that was already uploaded is left alone. Needs data/pages (see the README) and the saved
answers in data/eval_cache. The records are marked "(saved answer)": say so when you show them.
Writes into the database named in .env (DATABASE_URL), and images into data/storage.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import init_db  # noqa: E402
from app.evaluation import DATA  # noqa: E402
from app.services.demo_seed import DEFAULT_SOURCES, load_flip_pages, parse_source, seed_demo  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pages", help="comma separated page ids (default: every page with a saved answer)")
    ap.add_argument("--limit", type=int, help="seed at most this many pages")
    ap.add_argument("--prefer", action="append", metavar="PROVIDER:MODEL[:raw]",
                    help="saved answers to use, best first; ':raw' marks answers read without orientation correction. "
                         "Repeat for several. Default: gemini-2.5-flash (raw), gemini-3.5-flash, groq qwen3.8-27b")
    ap.add_argument("--dry-run", action="store_true", help="show what would be seeded, change nothing")
    args = ap.parse_args()

    if not args.dry_run:
        init_db()
    sources = tuple(parse_source(s) for s in args.prefer) if args.prefer else DEFAULT_SOURCES
    report = await seed_demo(
        DATA / "pages", DATA / "eval_cache", sources=sources, flip_pages=load_flip_pages(DATA / "sample_orientation.json"),
        pages=args.pages.split(",") if args.pages else None, limit=args.limit, dry_run=args.dry_run)

    print(f"{'would seed' if args.dry_run else 'seeded'}: {len(report.seeded)} pages")
    for label, count in sorted(report.by_source.items()):
        print(f"  {count:>3} from {label}")
    if report.already_there:
        print(f"already there (left alone): {len(report.already_there)}")
    if report.no_saved_answer:
        print(f"no saved answer: {len(report.no_saved_answer)}: {' '.join(report.no_saved_answer)}")
    if report.failed:
        print(f"FAILED: {' '.join(report.failed)}")


if __name__ == "__main__":
    asyncio.run(main())
