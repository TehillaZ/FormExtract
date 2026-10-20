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
    """The provider refused for lack of quota: it kept answering 429, or said the wait is too long to be worth it."""

    def __init__(self, where: str, retry_after: float | None = None):
        super().__init__(where)
        self.retry_after = retry_after   # seconds the provider asked us to wait, when it said


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


MAX_WAIT_SECONDS = 90   # a longer "retry in ..." means a daily quota: waiting here would only stall the batch

_RETRY_IN = re.compile(r"retry in (?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", re.IGNORECASE)


def retry_after_seconds(response: httpx.Response) -> float | None:
    """How long the provider says to wait: the Retry-After header, or "Please retry in 17h43m30.9s" in the body."""
    header = response.headers.get("retry-after")
    if header and header.isdigit():
        return float(header)
    match = _RETRY_IN.search(response.text)
    if not match or not any(match.groups()):
        return None
    hours, minutes, seconds = match.groups()
    return int(hours or 0) * 3600 + int(minutes or 0) * 60 + float(seconds or 0)


async def post_with_backoff(client, url: str, *, retries: int = 5, **kw):
    """POST, retrying on 429 / 5xx with exponential backoff (ADR-008). A 429 that asks for a long wait
    (an exhausted daily quota) raises RateLimited at once so the caller can move on to another model."""
    delay = 10.0
    host = httpx.URL(url).host
    for attempt in range(retries + 1):
        await _throttle(host)
        r = await client.post(url, **kw)
        if r.status_code not in (429, 500, 502, 503):
            r.raise_for_status()
            return r
        asked = retry_after_seconds(r)
        if r.status_code == 429 and asked is not None and asked > MAX_WAIT_SECONDS:
            raise RateLimited(url, asked)
        if attempt == retries:
            break
        await asyncio.sleep(asked if asked is not None else delay)
        delay = min(delay * 2, 60)
    if r.status_code == 429:
        raise RateLimited(url, retry_after_seconds(r))
    r.raise_for_status()


def make_client(timeout: float = 120) -> httpx.AsyncClient:
    """Use the OS trust store: on machines behind TLS-inspecting antivirus/proxies the bundled CA list fails."""
    return httpx.AsyncClient(timeout=timeout, verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT))
