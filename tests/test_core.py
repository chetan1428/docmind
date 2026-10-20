"""Unit tests: no Postgres or Redis needed, so they run fast in CI."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.chunking import chunk_text, extract_text
from app.embeddings import _hash_embed
from app.llm import extractive_answer, parse_grades


def test_chunk_text_respects_size_and_covers_text():
    text = " ".join(f"word{i}" for i in range(1000))
    chunks = chunk_text(text, size=200, overlap=40)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)
    assert chunks[0].startswith("word0")
    assert chunks[-1].endswith("word999")


def test_chunk_text_empty_and_bad_overlap():
    assert chunk_text("   \n  ") == []
    with pytest.raises(ValueError):
        chunk_text("hello", size=10, overlap=10)


def test_extract_text_rejects_unknown_type():
    assert extract_text("a.md", b"# hi") == "# hi"
    with pytest.raises(ValueError):
        extract_text("a.exe", b"xx")


def test_hash_embedding_is_normalized_and_similarity_makes_sense():
    a = np.array(_hash_embed("kubernetes pods run containers", 384))
    b = np.array(_hash_embed("containers run inside kubernetes pods", 384))
    c = np.array(_hash_embed("baking bread needs flour and yeast", 384))
    assert abs(np.linalg.norm(a) - 1.0) < 1e-5
    assert a @ b > a @ c


def test_extractive_answer_picks_relevant_sentence():
    text = (
        "Pods are the smallest unit. A readiness probe tells Kubernetes when a pod "
        "can receive traffic. Bread is tasty."
    )
    ctx = [{"filename": "k8s.md", "text": text}]
    ans = extractive_answer("what does a readiness probe do", ctx)
    assert "readiness probe" in ans and "[1]" in ans
    assert "Bread" not in ans


def test_parse_grades():
    assert parse_grades("1, 3", 4) == [0, 2]
    assert parse_grades("none", 4) == []
    assert parse_grades("Passages 2 and 9 and 2", 3) == [1]


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)  # not used as a context manager -> startup (DB) is skipped


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ask_validation(client):
    assert client.post("/api/ask", json={"question": ""}).status_code == 422
    assert client.post("/api/ask", json={"question": "valid q", "top_k": 99}).status_code == 422


def test_upload_rejects_bad_extension(client):
    r = client.post("/api/documents", files={"file": ("x.exe", b"data")})
    assert r.status_code == 400
