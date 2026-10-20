from functools import lru_cache

from openai import OpenAI

from app.config import settings


@lru_cache
def get_openai_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when a provider is set to 'openai'")
    return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
