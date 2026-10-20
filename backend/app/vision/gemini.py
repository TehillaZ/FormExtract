from __future__ import annotations

import base64
import time

from app.config import settings
from app.vision.base import RateLimited, VisionProvider, make_client, post_with_backoff

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiProvider(VisionProvider):
    """Gemini over REST. Free-tier quotas are per model, so when one model is out of quota the next one in
    `models` is tried. A model that said "retry in 17 hours" is skipped until then."""

    name = "gemini"

    def __init__(self, model: str | None = None, fallback_models: list[str] | None = None):
        self.model = model or settings.gemini_model
        fallbacks = settings.gemini_fallback_models if fallback_models is None else fallback_models
        self.models = [self.model, *[m for m in fallbacks if m != self.model]]
        self._cooling_until: dict[str, float] = {}

    def _available_models(self) -> list[str]:
        now = time.monotonic()
        return [m for m in self.models if self._cooling_until.get(m, 0.0) <= now]

    async def _complete(self, system: str, user: str, jpeg: bytes) -> str:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [
                {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(jpeg).decode()}},
                {"text": user},
            ]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        }
        last: RateLimited | None = None
        for model in self._available_models():
            try:
                async with make_client() as client:
                    r = await post_with_backoff(client, URL.format(model=model), json=body,
                                                headers={"x-goog-api-key": settings.gemini_api_key})
            except RateLimited as e:
                self._cooling_until[model] = time.monotonic() + (e.retry_after or 60.0)
                last = e
                continue
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        raise last or RateLimited("every Gemini model is cooling down")
