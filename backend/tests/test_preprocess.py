import cv2
import numpy as np

from app.pipeline.preprocess import deskew, estimate_skew, fix_perspective, preprocess


def _text_page(h=1400, w=1000):
    img = np.full((h, w, 3), 255, np.uint8)
    for y in range(100, h - 100, 40):
        cv2.line(img, (80, y), (w - 80, y), (0, 0, 0), 3)
    return img


def test_skew_is_detected_and_fixed():
    page = _text_page()
    rotated = deskew(page, 5.0)
    angle = estimate_skew(cv2.cvtColor(rotated, cv2.COLOR_BGR2GRAY))
    assert 3.5 < abs(angle) < 6.5
    fixed = preprocess(rotated)
    assert any(s.startswith("deskew") for s in fixed.steps)


def test_straight_page_untouched():
    res = preprocess(_text_page())
    assert not any(s.startswith("deskew") for s in res.steps)


def test_perspective_finds_sheet_on_dark_table():
    canvas = np.full((1600, 1200, 3), 40, np.uint8)
    sheet = np.array([[200, 150], [1000, 220], [950, 1450], [180, 1380]], np.int32)
    cv2.fillPoly(canvas, [sheet], (250, 250, 250))
    flat = fix_perspective(canvas)
    assert flat is not None
    assert flat.mean() > 200  # mostly paper now


def test_perspective_none_for_plain_scan():
    assert fix_perspective(_text_page()) is None


def test_deskew_round_trip_levels_the_page():
    for tilt in (4.0, -3.0):
        tilted = deskew(_text_page(), tilt)
        fixed = preprocess(tilted).image
        residual = estimate_skew(cv2.cvtColor(fixed, cv2.COLOR_BGR2GRAY))
        assert abs(residual) < 0.5, (tilt, residual)
