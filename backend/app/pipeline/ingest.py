"""Turn an uploaded file (PDF / image / HEIC) into a list of page images (BGR numpy arrays)."""
from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from PIL import Image, ImageOps

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # HEIC support is optional
    pass

PDF_DPI = 200  # enough for OCR / vision models, keeps images ~1650x2350
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".heic", ".heif"}


def _pil_to_bgr(img: Image.Image) -> np.ndarray:
    img = ImageOps.exif_transpose(img)  # phone photos carry rotation in EXIF
    img = img.convert("RGB")
    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


def pdf_to_images(data: bytes, dpi: int = PDF_DPI) -> list[np.ndarray]:
    pages: list[np.ndarray] = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
            pages.append(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
    return pages


def image_to_images(data: bytes) -> list[np.ndarray]:
    """An image file may hold several frames (multi-page TIFF)."""
    img = Image.open(io.BytesIO(data))
    frames = []
    for i in range(getattr(img, "n_frames", 1)):
        img.seek(i)
        frames.append(_pil_to_bgr(img.copy()))
    return frames


def file_to_images(filename: str, data: bytes) -> list[np.ndarray]:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf" or data[:5] == b"%PDF-":
        return pdf_to_images(data)
    if ext in IMAGE_EXTS or not ext:
        return image_to_images(data)
    raise ValueError(f"Unsupported file type: {ext}")
