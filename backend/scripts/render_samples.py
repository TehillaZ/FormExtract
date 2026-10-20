"""Render sample PDFs to page PNGs and decode barcodes on each page.

Usage: python -m scripts.render_samples <pdf> [<pdf> ...] --out ../data/pages
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from app.pipeline.barcodes import decode_barcodes
from app.pipeline.ingest import file_to_images


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", default="../data/pages")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = []
    for part, f in enumerate(args.files, start=1):
        path = Path(f)
        pages = file_to_images(path.name, path.read_bytes())
        for i, img in enumerate(pages, start=1):
            page_id = f"p{part}_{i:02d}"
            cv2.imwrite(str(out / f"{page_id}.png"), img)
            codes = decode_barcodes(img)
            report.append({"page": page_id, "size": img.shape[1::-1],
                           "barcodes": [{"text": c.text, "format": c.format, "box": c.box} for c in codes]})
            print(page_id, [(c.format, c.text) for c in codes])
    (out / "barcodes.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
