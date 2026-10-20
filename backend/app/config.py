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
    gemini_model: str = "gemini-2.5-flash"
    groq_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    vision_provider: Literal["gemini", "groq"] = "gemini"
    vision_fallback_provider: Literal["gemini", "groq"] = "groq"
    id_checksum_mode: Literal["strict", "lenient"] = "strict"
    max_concurrency: int = 2
    min_call_interval: float = 7.0   # seconds between calls to one provider (free-tier RPM limits)
    database_url: str = ""
    storage_dir: str = "./data/storage"


settings = Settings()
