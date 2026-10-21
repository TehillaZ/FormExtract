"""Local barcode decoding (no data leaves the machine)."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
import zxingcpp


@dataclass
class Barcode:
    text: str
    format: str
    # bounding box in page pixel coordinates: x, y, w, h
    box: tuple[int, int, int, int]


def _box(position) -> tuple[int, int, int, int]:
    pts = [position.top_left, position.top_right, position.bottom_right, position.bottom_left]
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


UPSCALE = 1.5   # small barcodes on a full page decode better enlarged: +5 numbers over 48 pages for ~0.3 s a page.
                # 2x or tile-by-tile scanning found one more at three times the cost; other filters found none.


def decode_barcodes(img_bgr: np.ndarray) -> list[Barcode]:
    """Every valid barcode on the page. The page is read as it is, binarized (helps faint scans), and enlarged.
    Boxes are always in the coordinates of the page that was passed in."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if img_bgr.ndim == 3 else img_bgr
    binarized = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
    enlarged = cv2.resize(gray, None, fx=UPSCALE, fy=UPSCALE, interpolation=cv2.INTER_CUBIC)
    found: dict[str, Barcode] = {}
    for img, scale in ((gray, 1.0), (binarized, 1.0), (enlarged, UPSCALE)):
        for r in zxingcpp.read_barcodes(img, try_rotate=True, try_downscale=True):
            if r.valid and r.text and r.text not in found:
                x, y, w, h = _box(r.position)
                found[r.text] = Barcode(r.text, r.format.name, (round(x / scale), round(y / scale), round(w / scale), round(h / scale)))
    return list(found.values())
