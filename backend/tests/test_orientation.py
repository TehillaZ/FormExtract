import cv2
import numpy as np

from app.pipeline.orientation import correct_quarter_turn, flip_180, is_sideways, line_directions


def page_with_text_lines(lines: int = 24, words_per_line: int = 8) -> np.ndarray:
    """A white page with rows of word-sized text, like a typed form. Upright: lines run horizontally."""
    img = np.full((1100, 800, 3), 255, np.uint8)
    for i in range(lines):
        y = 80 + i * 38
        for j in range(words_per_line):
            cv2.putText(img, "abc 123", (60 + j * 90, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    return img


def gray(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def test_upright_page_is_not_sideways():
    assert not is_sideways(gray(page_with_text_lines()))


def test_page_turned_a_quarter_is_sideways_either_way():
    page = page_with_text_lines()
    assert is_sideways(gray(cv2.rotate(page, cv2.ROTATE_90_CLOCKWISE)))
    assert is_sideways(gray(cv2.rotate(page, cv2.ROTATE_90_COUNTERCLOCKWISE)))


def test_upside_down_page_is_not_sideways():
    # 180 degrees keeps the lines horizontal: only the model can tell this one
    assert not is_sideways(gray(flip_180(page_with_text_lines())))


def test_correct_quarter_turn_makes_text_horizontal_again():
    sideways = cv2.rotate(page_with_text_lines(), cv2.ROTATE_90_COUNTERCLOCKWISE)
    fixed, turned = correct_quarter_turn(sideways)
    assert turned and not is_sideways(gray(fixed))
    assert fixed.shape[0] > fixed.shape[1]   # portrait again


def test_upright_page_is_left_alone():
    page = page_with_text_lines()
    fixed, turned = correct_quarter_turn(page)
    assert not turned and fixed is page


def test_scan_edge_bar_does_not_fool_it():
    page = page_with_text_lines()
    cv2.rectangle(page, (770, 0), (780, 1099), (0, 0, 0), -1)   # thick black bar like a scanner edge
    assert not is_sideways(gray(page))


def test_blank_or_nearly_empty_page_is_not_judged():
    blank = np.full((1100, 800), 255, np.uint8)
    assert line_directions(blank) is None
    assert not is_sideways(blank)
