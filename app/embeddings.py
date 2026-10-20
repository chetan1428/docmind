"""Embedding providers.

`hash` is a feature-hashing bag-of-words embedder: no model download, no API
key, tiny Docker image. It is good enough to make retrieval work on keyword
overlap, so you can focus on deployment. Switch EMBEDDING_PROVIDER=openai
for real semantic embeddings (re-ingest documents after switching).
"""

import hashlib
import re

import numpy as np

from app.config import settings

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an and are as at be by for from has have how i in is it its of on or that the this "
    "to was what when where which who why will with you your do does can".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


def _hash_embed(text: str, dim: int) -> list[float]:
    vec = np.zeros(dim, dtype=np.float32)
    tokens = tokenize(text)
    features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False)]  # unigrams + bigrams
    for feat in features:
        h = int.from_bytes(hashlib.md5(feat.encode()).digest()[:8], "little")
        vec[h % dim] += 1.0 if (h >> 63) & 1 else -1.0
    norm = float(np.linalg.norm(vec))
    return (vec / norm).tolist() if norm else vec.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    if settings.embedding_provider == "openai":
        from app.ai_client import get_openai_client

        client = get_openai_client()
        out: list[list[float]] = []
        for i in range(0, len(texts), 64):
            resp = client.embeddings.create(
                model=settings.embedding_model,
                input=texts[i : i + 64],
                dimensions=settings.embedding_dim,
            )
            out.extend(d.embedding for d in resp.data)
        return out
    return [_hash_embed(t, settings.embedding_dim) for t in texts]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
