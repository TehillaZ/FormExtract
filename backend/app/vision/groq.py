from __future__ import annotations

import base64

from app.config import settings
from app.vision.base import VisionProvider, make_client, post_with_backoff


class GroqProvider(VisionProvider):
    name = "groq"

    def __init__(self, model: str | None = None):
        self.model = model or settings.groq_model

    async def _complete(self, system: str, user: str, jpeg: bytes) -> str:
        data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": [
                    {"type": "text", "text": user},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ]},
            ],
        }
        async with make_client() as client:
            r = await post_with_backoff(
                client, "https://api.groq.com/openai/v1/chat/completions", json=body,
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            )
        return r.json()["choices"][0]["message"]["content"]
