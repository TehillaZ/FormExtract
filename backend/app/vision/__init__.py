from app.vision.base import RateLimited, VisionProvider


def get_provider(name: str, model: str | None = None, fallback_models: list[str] | None = None) -> VisionProvider:
    """`fallback_models=[]` pins a Gemini provider to its one model (None means: use the configured fallbacks)."""
    if name == "gemini":
        from app.vision.gemini import GeminiProvider
        return GeminiProvider(model, fallback_models)
    if name == "groq":
        from app.vision.groq import GroqProvider
        return GroqProvider(model)
    raise ValueError(f"unknown provider: {name}")


__all__ = ["VisionProvider", "RateLimited", "get_provider"]
