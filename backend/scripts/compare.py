"""Compare two cached runs page by page, on exactly the pages both of them scored. No API calls.

  python scripts/compare.py --a gemini:gemini-3.5-flash --b groq:qwen/qwen3.8-27b --split dev
  python scripts/compare.py --a gemini:gemini-3.5-flash --b groq:qwen/qwen3.8-27b --split dev --detail

Each side is `provider:model`. Runs are made first with scripts/evaluate.py (which fills the cache).
A run made with `--no-orient` is read back with --a-no-orient / --b-no-orient. Orientation correction changes
nothing on an upright page, so `--skip-sideways` makes a run with it and a run without it comparable.
Per field it shows how many pages each was right on, where only one of them was, and the errors that were not
flagged. `--detail` lists the pages where they disagree.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.evaluation import (  # noqa: E402
    DATA, Outcome, cache_tag, compare_paired, format_paired, load_split, load_truth, score_record,
)
from app.pipeline.barcodes import decode_barcodes  # noqa: E402
from app.pipeline.extract import build_record  # noqa: E402
from app.pipeline.orientation import correct_quarter_turn, is_sideways  # noqa: E402
from app.schemas import RawExtraction  # noqa: E402


def cached_outcomes(provider: str, model: str, oriented: bool, truth: dict[str, dict]) -> tuple[dict[str, dict[str, Outcome]], Path]:
    """page -> field -> (correct, flagged), for every page this run has cached."""
    folder = DATA / "eval_cache" / cache_tag(provider, model, oriented)
    out: dict[str, dict[str, Outcome]] = {}
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        page = path.stem
        if page not in truth:
            continue
        raw = RawExtraction.model_validate_json(path.read_text(encoding="utf-8"))
        img = cv2.imread(str(DATA / "pages" / f"{page}.png"))
        seen = correct_quarter_turn(img)[0] if oriented else img   # barcodes are read from the turned page
        rec = build_record(raw, [b.text for b in decode_barcodes(seen)], provider=provider)
        out[page] = score_record(rec, truth[page])
    return out, folder


def split_spec(spec: str) -> tuple[str, str]:
    provider, _, model = spec.partition(":")
    if not model:
        raise SystemExit(f"'{spec}' should look like provider:model, e.g. gemini:gemini-3.5-flash")
    return provider, model


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", required=True, help="provider:model")
    ap.add_argument("--b", required=True, help="provider:model")
    ap.add_argument("--split", choices=["dev", "test"], help="only pages of this split (the test set: final numbers only)")
    ap.add_argument("--no-orient", action="store_true", help="read both caches as made without orientation correction")
    ap.add_argument("--a-no-orient", action="store_true", help="run A was made without orientation correction")
    ap.add_argument("--b-no-orient", action="store_true", help="run B was made without orientation correction")
    ap.add_argument("--skip-sideways", action="store_true", help="leave out sideways pages, where orientation matters")
    ap.add_argument("--detail", action="store_true", help="list the pages where the two disagree")
    args = ap.parse_args()

    truth = load_truth()
    if args.split:
        wanted = load_split(args.split)
        truth = {p: t for p, t in truth.items() if p in wanted}
    if args.skip_sideways:
        upright = {p for p in truth if not is_sideways(cv2.cvtColor(cv2.imread(str(DATA / "pages" / f"{p}.png")), cv2.COLOR_BGR2GRAY))}
        print(f"leaving out {len(truth) - len(upright)} sideways pages: {' '.join(sorted(set(truth) - upright))}")
        truth = {p: t for p, t in truth.items() if p in upright}
    (pa, ma), (pb, mb) = split_spec(args.a), split_spec(args.b)
    a, folder_a = cached_outcomes(pa, ma, not (args.no_orient or args.a_no_orient), truth)
    b, folder_b = cached_outcomes(pb, mb, not (args.no_orient or args.b_no_orient), truth)

    print(f"A = {args.a}: {len(a)} pages cached ({folder_a.name})")
    print(f"B = {args.b}: {len(b)} pages cached ({folder_b.name})")
    paired = compare_paired(a, b)
    if not paired:
        print("\nNo page was scored by both runs. Run scripts/evaluate.py for each side first.")
        return
    print()
    print(format_paired(paired, args.a, args.b))
    print("\nsilent = wrong and not flagged: the errors that would reach the database unnoticed.")
    if args.detail:
        shared = sorted(set(a) & set(b))
        for field in paired:
            only_a = [p for p in shared if a[p][field][0] and not b[p][field][0]]
            only_b = [p for p in shared if b[p][field][0] and not a[p][field][0]]
            if only_a or only_b:
                print(f"\n{field}\n  only A right: {' '.join(only_a) or '-'}\n  only B right: {' '.join(only_b) or '-'}")


if __name__ == "__main__":
    main()
