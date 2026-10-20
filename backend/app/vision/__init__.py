from app.vision.base import RateLimited, VisionProvider


def get_provider(name: str, model: str | None = None) -> VisionProvider:
    if name == "gemini":
        from app.vision.gemini import GeminiProvider
        return GeminiProvider(model)
    if name == "groq":
        from app.vision.groq import GroqProvider
        return GroqProvider(model)
    raise ValueError(f"unknown provider: {name}")


__all__ = ["VisionProvider", "RateLimited", "get_provider"]
