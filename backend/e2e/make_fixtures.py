"""Writes the three small page images the browser tests upload. Their WIDTH selects the scripted answer
(see server.py), and the different sizes give each file a different hash, so none counts as a duplicate.

  python -m e2e.make_fixtures
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

OUT = Path(__file__).resolve().parents[2] / "frontend" / "e2e" / "fixtures"
HEIGHT = 800


def page(width: int, title: str) -> np.ndarray:
    img = np.full((HEIGHT, width, 3), 255, np.uint8)
    cv2.putText(img, title, (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (30, 30, 30), 2, cv2.LINE_AA)
    for row in range(14):   # horizontal lines of text, so the page is not mistaken for a sideways scan
        for col in range(5):
            cv2.putText(img, "abc 123", (30 + col * 105, 130 + row * 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (60, 60, 60), 1, cv2.LINE_AA)
    return img


def marked_page() -> np.ndarray:
    """Form D, upright: a solid black block in the top-left corner tells the scripted model which way is up."""
    img = page(630, "FORM D")
    cv2.rectangle(img, (10, 10), (110, 110), (0, 0, 0), -1)
    return img


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    pages = {name: page(width, name.upper()) for name, width in (("form-a", 600), ("form-b", 610), ("form-c", 620))}
    # scans that arrive turned: the pipeline must find the right way up before the model reads them
    pages["sideways"] = cv2.rotate(pages["form-a"], cv2.ROTATE_90_COUNTERCLOCKWISE)        # one clockwise turn fixes it
    pages["upside-down"] = cv2.rotate(marked_page(), cv2.ROTATE_180)                       # only the model can tell
    pages["sideways-flipped"] = cv2.rotate(marked_page(), cv2.ROTATE_90_CLOCKWISE)         # turned, then still upside down
    for name, img in pages.items():
        cv2.imwrite(str(OUT / f"{name}.png"), img)
        print("wrote", OUT / f"{name}.png", img.shape[1], "x", img.shape[0])
