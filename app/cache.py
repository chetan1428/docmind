"""Redis: answer cache + job-queue connection."""

import hashlib
import json

from redis import Redis

from app.config import settings

# decode_responses=True for our JSON cache; RQ needs raw bytes, so a second client.
redis_cache = Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=3)
redis_queue = Redis.from_url(settings.redis_url, socket_timeout=None)

_CORPUS_VERSION_KEY = "docmind:corpus_version"


def redis_ok() -> bool:
    try:
        return bool(redis_cache.ping())
    except Exception:  # noqa: BLE001
        return False


def bump_corpus_version() -> None:
    """Called whenever documents change, so stale cached answers are never served."""
    try:
        redis_cache.incr(_CORPUS_VERSION_KEY)
    except Exception:  # noqa: BLE001
        pass


def _key(question: str, top_k: int) -> str:
    version = redis_cache.get(_CORPUS_VERSION_KEY) or "0"
    providers = f"{settings.llm_provider}|{settings.embedding_provider}"
    raw = f"{version}|{providers}|{top_k}|{question.strip().lower()}"
    return "docmind:ask:" + hashlib.sha256(raw.encode()).hexdigest()


def get_cached(question: str, top_k: int) -> dict | None:
    try:
        val = redis_cache.get(_key(question, top_k))
        return json.loads(val) if val else None
    except Exception:  # noqa: BLE001
        return None  # cache is best-effort; never fail a request because of it


def set_cached(question: str, top_k: int, payload: dict) -> None:
    try:
        redis_cache.setex(_key(question, top_k), settings.cache_ttl_seconds, json.dumps(payload))
    except Exception:  # noqa: BLE001
        pass
