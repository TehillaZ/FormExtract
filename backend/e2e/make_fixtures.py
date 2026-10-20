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


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, width in (("form-a", 600), ("form-b", 610), ("form-c", 620)):
        cv2.imwrite(str(OUT / f"{name}.png"), page(width, name.upper()))
        print("wrote", OUT / f"{name}.png")
