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


def decode_barcodes(img_bgr: np.ndarray) -> list[Barcode]:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if img_bgr.ndim == 3 else img_bgr
    found: dict[str, Barcode] = {}
    # try the plain image first, then a binarized copy (helps faint scans)
    candidates = [gray, cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)]
    for img in candidates:
        for r in zxingcpp.read_barcodes(img, try_rotate=True, try_downscale=True):
            if r.valid and r.text and r.text not in found:
                found[r.text] = Barcode(r.text, r.format.name, _box(r.position))
    return list(found.values())
