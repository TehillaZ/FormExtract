"""Settings from environment / .env (see PLAN ADR-003, ADR-008, ADR-014)."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    gemini_api_key: str = ""
    groq_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"   # measured best and fast (about 12 s a page); 3.5-flash takes about 100 s
    # tried in order when the model before it is out of free-tier quota (quotas are per model)
    gemini_fallback_models: list[str] = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.5-flash"]
    groq_model: str = "qwen/qwen3.8-27b"   # the only Groq model that reads images (llama-4-scout was withdrawn)
    vision_provider: Literal["gemini", "groq"] = "gemini"
    vision_fallback_provider: Literal["gemini", "groq"] = "groq"
    id_checksum_mode: Literal["strict", "lenient"] = "strict"
    max_concurrency: int = 2
    min_call_interval: float = 7.0   # seconds between calls to one provider (free-tier RPM limits)
    database_url: str = ""
    storage_dir: str = "./data/storage"
    user_password: str = ""        # the "user" role; empty means nobody can log in as a user
    developer_password: str = ""   # the "developer" role (accuracy and repeated-mistakes screens)

    def has_api_key(self, provider: str) -> bool:
        return bool(getattr(self, f"{provider}_api_key"))


settings = Settings()
