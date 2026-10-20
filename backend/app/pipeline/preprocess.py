"""Local image cleanup before any model call: perspective, deskew, contrast.

Every step is conservative: if it cannot find what it needs, it returns the
input unchanged rather than guessing.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

MAX_DESKEW_DEG = 15.0


@dataclass
class PreprocessResult:
    image: np.ndarray
    steps: list[str] = field(default_factory=list)
    low_quality: bool = False


def _order_corners(pts: np.ndarray) -> np.ndarray:
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype=np.float32)


def fix_perspective(img: np.ndarray) -> np.ndarray | None:
    """Find the paper sheet in a phone photo and flatten it. None if no clear sheet."""
    h, w = img.shape[:2]
    scale = 1000 / max(h, w)
    small = cv2.resize(img, None, fx=scale, fy=scale) if scale < 1 else img.copy()
    scale = min(scale, 1.0)
    gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    edges = cv2.dilate(cv2.Canny(gray, 50, 150), np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area_small = small.shape[0] * small.shape[1]
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
        area = cv2.contourArea(approx)
        # sheet must be a quad covering a real part of the photo, but not the whole frame (= already a scan)
        if len(approx) == 4 and 0.25 * area_small < area < 0.95 * area_small:
            src = _order_corners(approx.reshape(4, 2).astype(np.float32) / scale)
            tl, tr, br, bl = src
            width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
            height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
            dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
            return cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (width, height))
    return None


def _profile_score(binary: np.ndarray, angle: float) -> float:
    h, w = binary.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    rot = cv2.warpAffine(binary, m, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
    rows = rot.sum(axis=1, dtype=np.float64)
    return float(np.var(np.diff(rows)))


def estimate_skew(gray: np.ndarray) -> float:
    """Small-angle skew in degrees (projection profile: text rows are sharpest when level)."""
    scale = 800 / gray.shape[1]
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    binary = cv2.threshold(small, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coarse = max(np.arange(-MAX_DESKEW_DEG, MAX_DESKEW_DEG + 0.01, 1.0), key=lambda a: _profile_score(binary, a))
    fine = max(np.arange(coarse - 1, coarse + 1.01, 0.1), key=lambda a: _profile_score(binary, a))
    return float(fine)


def deskew(img: np.ndarray, angle: float) -> np.ndarray:
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))


def is_dark(gray: np.ndarray) -> bool:
    return float(np.mean(gray)) < 150


def enhance_contrast(img: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    lightness, a, b = cv2.split(lab)
    lightness = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lightness)
    return cv2.cvtColor(cv2.merge((lightness, a, b)), cv2.COLOR_LAB2BGR)


def blur_score(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def preprocess(img: np.ndarray, is_photo: bool = False) -> PreprocessResult:
    res = PreprocessResult(image=img)
    if is_photo:
        flat = fix_perspective(res.image)
        if flat is not None:
            res.image = flat
            res.steps.append("perspective")
    gray = cv2.cvtColor(res.image, cv2.COLOR_BGR2GRAY)
    angle = estimate_skew(gray)
    if 0.3 <= abs(angle) <= MAX_DESKEW_DEG:
        res.image = deskew(res.image, angle)
        res.steps.append(f"deskew:{angle:.1f}")
        gray = cv2.cvtColor(res.image, cv2.COLOR_BGR2GRAY)
    if is_dark(gray):
        res.image = enhance_contrast(res.image)
        res.steps.append("contrast")
        gray = cv2.cvtColor(res.image, cv2.COLOR_BGR2GRAY)
    if blur_score(gray) < 50:
        res.low_quality = True
        res.steps.append("low_quality")
    return res
