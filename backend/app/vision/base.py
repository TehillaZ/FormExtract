"""Swappable vision provider interface (PLAN ADR-003)."""
from __future__ import annotations

import asyncio
import json
import re
import ssl
import time
from abc import ABC, abstractmethod

import cv2
import httpx
import numpy as np
import truststore

from app.config import settings
from app.schemas import RawExtraction
from app.vision.prompt import SYSTEM_PROMPT, USER_PROMPT


class RateLimited(Exception):
    """Provider kept answering 429 after backoff."""


class VisionProvider(ABC):
    name: str

    @abstractmethod
    async def _complete(self, system: str, user: str, jpeg: bytes) -> str:
        """Send one image + prompts, return the raw text of the model's JSON answer."""

    async def extract(self, img_bgr: np.ndarray, hint: str = "") -> RawExtraction:
        jpeg = encode_jpeg(img_bgr)
        text = await self._complete(SYSTEM_PROMPT + (f"\n\nTEMPLATE HINTS\n{hint}" if hint else ""), USER_PROMPT, jpeg)
        return parse_extraction(text)


def encode_jpeg(img_bgr: np.ndarray, max_side: int = 2000, quality: int = 88) -> bytes:
    h, w = img_bgr.shape[:2]
    scale = max_side / max(h, w)
    if scale < 1:
        img_bgr = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("could not encode image")
    return buf.tobytes()


def parse_extraction(text: str) -> RawExtraction:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return RawExtraction.model_validate(json.loads(text))


_last_call: dict[str, float] = {}
_locks: dict[str, asyncio.Lock] = {}


async def _throttle(key: str) -> None:
    """Space calls to one provider by min_call_interval, even when pages are processed concurrently."""
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        wait = _last_call.get(key, 0.0) + settings.min_call_interval - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call[key] = time.monotonic()


async def post_with_backoff(client, url: str, *, retries: int = 5, **kw):
    """POST, retrying on 429 / 5xx with exponential backoff (ADR-008)."""
    delay = 10.0
    host = httpx.URL(url).host
    for attempt in range(retries + 1):
        await _throttle(host)
        r = await client.post(url, **kw)
        if r.status_code not in (429, 500, 502, 503):
            r.raise_for_status()
            return r
        if attempt == retries:
            break
        retry_after = r.headers.get("retry-after")
        await asyncio.sleep(float(retry_after) if retry_after and retry_after.isdigit() else delay)
        delay = min(delay * 2, 60)
    if r.status_code == 429:
        raise RateLimited(url)
    r.raise_for_status()


def make_client(timeout: float = 120) -> httpx.AsyncClient:
    """Use the OS trust store: on machines behind TLS-inspecting antivirus/proxies the bundled CA list fails."""
    return httpx.AsyncClient(timeout=timeout, verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT))
