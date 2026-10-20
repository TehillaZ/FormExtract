from __future__ import annotations

import base64

from app.config import settings
from app.vision.base import VisionProvider, make_client, post_with_backoff


class GeminiProvider(VisionProvider):
    name = "gemini"

    def __init__(self, model: str | None = None):
        self.model = model or settings.gemini_model

    async def _complete(self, system: str, user: str, jpeg: bytes) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [
                {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(jpeg).decode()}},
                {"text": user},
            ]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        }
        async with make_client() as client:
            r = await post_with_backoff(client, url, json=body, headers={"x-goog-api-key": settings.gemini_api_key})
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
