"""Page orientation without OCR (PLAN ADR-009).

Sideways pages (90 or 270 degrees) are found locally: if the text lines run vertically, the page is turned a
quarter. That leaves upright versus upside down, which only the vision model can judge: the extraction answer
includes `text_upside_down`, and the caller flips the page and asks again (see process.extract_oriented).
"""
from __future__ import annotations

import cv2
import numpy as np

WORK_SIZE = 1000          # long side the page is shrunk to before analysis
SIDEWAYS_RATIO = 1.5      # vertical-line structure must beat horizontal by this factor
MIN_CHARACTERS = 30       # fewer character-like blobs than this: not enough text to judge
MARGIN = 0.03             # ignore the page border (scan edges)


def _character_centres(gray: np.ndarray) -> tuple[np.ndarray, int, int]:
    """Centres of character-sized blobs, after removing long lines (scan edges, form rules)."""
    h, w = gray.shape
    scale = WORK_SIZE / max(h, w)
    small = cv2.resize(gray, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    _, ink = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    height, width = ink.shape
    for kernel in ((int(width * 0.22), 1), (1, int(height * 0.22))):
        lines = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, kernel))
        ink = cv2.subtract(ink, cv2.dilate(lines, np.ones((3, 3), np.uint8)))

    count, _, stats, centroids = cv2.connectedComponentsWithStats(ink, connectivity=8)
    box_w, box_h, area = stats[1:, cv2.CC_STAT_WIDTH], stats[1:, cv2.CC_STAT_HEIGHT], stats[1:, cv2.CC_STAT_AREA]
    is_char = (box_w >= 2) & (box_w <= 60) & (box_h >= 3) & (box_h <= 60) & (area >= 6)
    return centroids[1:][is_char], height, width


def _peakiness(values: np.ndarray, bins: int = 120) -> float:
    """How unevenly the values pile up in a few bins. Text lines make centres pile up on few rows or columns."""
    hist, _ = np.histogram(values, bins=bins)
    hist = hist.astype(float)
    return float(hist.var() / (hist.mean() ** 2 + 1e-9))


def line_directions(gray: np.ndarray) -> tuple[float, float] | None:
    """(horizontal, vertical) text-line strength, or None when the page has too little text to tell."""
    centres, height, width = _character_centres(gray)
    inside = ((centres[:, 0] > width * MARGIN) & (centres[:, 0] < width * (1 - MARGIN))
              & (centres[:, 1] > height * MARGIN) & (centres[:, 1] < height * (1 - MARGIN)))
    centres = centres[inside]
    if len(centres) < MIN_CHARACTERS:
        return None
    return _peakiness(centres[:, 1]), _peakiness(centres[:, 0])


def is_sideways(gray: np.ndarray) -> bool:
    strength = line_directions(gray)
    return strength is not None and strength[1] > SIDEWAYS_RATIO * strength[0]


def correct_quarter_turn(img_bgr: np.ndarray) -> tuple[np.ndarray, bool]:
    """Turn a sideways page 90 degrees clockwise. Returns (image, turned). It may still be upside down."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if img_bgr.ndim == 3 else img_bgr
    if not is_sideways(gray):
        return img_bgr, False
    return cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE), True


def flip_180(img_bgr: np.ndarray) -> np.ndarray:
    return cv2.rotate(img_bgr, cv2.ROTATE_180)
