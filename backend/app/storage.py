"""Image storage behind a small interface so local disk can be swapped for cloud storage later (ADR-006)."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from app.config import ROOT, settings


class Storage(Protocol):
    def save_image(self, key: str, img_bgr: np.ndarray) -> str: ...
    def read_image(self, path: str) -> np.ndarray: ...
    def abspath(self, path: str) -> Path: ...


class LocalStorage:
    def __init__(self, root: str | Path | None = None):
        root = Path(root or settings.storage_dir)
        self.root = root if root.is_absolute() else ROOT / root

    def save_image(self, key: str, img_bgr: np.ndarray) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        ok, buf = cv2.imencode(path.suffix or ".png", img_bgr)
        if not ok:
            raise ValueError("could not encode image")
        path.write_bytes(buf.tobytes())
        return key

    def abspath(self, path: str) -> Path:
        full = (self.root / path).resolve()
        if not full.is_relative_to(self.root.resolve()):   # never serve anything outside the storage root
            raise ValueError("bad path")
        return full

    def read_image(self, path: str) -> np.ndarray:
        img = cv2.imdecode(np.frombuffer(self.abspath(path).read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("unreadable image")
        return img


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage


def set_storage(storage: Storage) -> None:
    global _storage
    _storage = storage
