"""DocMind API: upload documents, ask questions over them (RAG)."""

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field
from rq import Queue
from sqlalchemy import select

from app.cache import bump_corpus_version, get_cached, redis_ok, redis_queue, set_cached
from app.chunking import SUPPORTED_EXTENSIONS, extract_text
from app.config import settings
from app.db import Document, SessionLocal, db_ok, init_db
from app.embeddings import tokenize
from app.rag_graph import run_rag
from app.worker import QUEUE_NAME

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s [api] %(name)s: %(message)s")
log = logging.getLogger("docmind")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    log.info(
        "%s %s started (llm=%s, embeddings=%s)",
        settings.app_name,
        settings.app_version,
        settings.llm_provider,
        settings.embedding_provider,
    )
    if settings.llm_provider == "groq" and not settings.groq_api_key:
        log.warning("LLM_PROVIDER=groq but GROQ_API_KEY is not set: /api/ask will fail until it is")
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)
Instrumentator().instrument(app).expose(app, include_in_schema=False)  # GET /metrics


def ingest_queue() -> Queue:
    return Queue(QUEUE_NAME, connection=redis_queue)


# ---------- Schemas ----------
class DocumentOut(BaseModel):
    id: int
    filename: str
    status: str
    num_chunks: int
    error: str | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=10)


class Source(BaseModel):
    document_id: int
    filename: str
    chunk_index: int
    text: str
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    search_query: str
    steps: list[str]  # LangGraph nodes visited, e.g. retrieve → grade → rewrite → retrieve → ...
    cached: bool
    latency_ms: int


def _doc_out(d: Document) -> DocumentOut:
    return DocumentOut(id=d.id, filename=d.filename, status=d.status, num_chunks=d.num_chunks, error=d.error)


# ---------- Health (for Docker HEALTHCHECK / K8s probes / ALB target groups) ----------
@app.get("/health", tags=["ops"])
def health():
    """Liveness: the process is up. Does NOT check dependencies."""
    return {"status": "ok", "version": settings.app_version}


@app.get("/ready", tags=["ops"])
def ready():
    """Readiness: can we actually serve traffic? Checks Postgres and Redis."""
    checks = {"database": db_ok(), "redis": redis_ok()}
    status = 200 if all(checks.values()) else 503
    return JSONResponse({"ready": status == 200, "checks": checks}, status_code=status)


# ---------- Documents ----------
@app.post("/api/documents", response_model=DocumentOut, status_code=202, tags=["documents"])
def upload_document(file: Annotated[UploadFile, File()]):
    filename = Path(file.filename or "upload.txt").name
    if not filename.lower().endswith(SUPPORTED_EXTENSIONS):
        raise HTTPException(400, f"Unsupported file type. Allowed: {', '.join(SUPPORTED_EXTENSIONS)}")

    data = file.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {settings.max_upload_mb} MB)")
    try:
        content = extract_text(filename, data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Could not read file: {exc}") from exc
    if not content.strip():
        raise HTTPException(400, "No text found in file (scanned PDFs are not supported)")

    with SessionLocal() as session:
        doc = Document(filename=filename, content=content, status="queued")
        session.add(doc)
        session.commit()
        session.refresh(doc)

    ingest_queue().enqueue("app.tasks.ingest_document", doc.id, job_timeout=600)
    log.info("Queued document %s (%s, %d chars)", doc.id, filename, len(content))
    return _doc_out(doc)


@app.get("/api/documents", response_model=list[DocumentOut], tags=["documents"])
def list_documents():
    with SessionLocal() as session:
        docs = session.scalars(select(Document).order_by(Document.id.desc())).all()
        return [_doc_out(d) for d in docs]


@app.get("/api/documents/{doc_id}", response_model=DocumentOut, tags=["documents"])
def get_document(doc_id: int):
    with SessionLocal() as session:
        doc = session.get(Document, doc_id)
        if doc is None:
            raise HTTPException(404, "Document not found")
        return _doc_out(doc)


@app.delete("/api/documents/{doc_id}", status_code=204, tags=["documents"])
def delete_document(doc_id: int):
    with SessionLocal() as session:
        doc = session.get(Document, doc_id)
        if doc is None:
            raise HTTPException(404, "Document not found")
        session.delete(doc)
        session.commit()
    bump_corpus_version()


# ---------- Ask ----------
@app.post("/api/ask", response_model=AskResponse, tags=["ask"])
def ask(req: AskRequest):
    started = time.perf_counter()
    top_k = req.top_k or settings.top_k
    question = req.question.strip()

    cached = get_cached(question, top_k)
    if cached:
        cached.update(cached=True, latency_ms=int((time.perf_counter() - started) * 1000))
        return cached

    if settings.embedding_provider == "hash" and not tokenize(question):
        raise HTTPException(400, "Question has no searchable words")

    try:
        result = run_rag(question, top_k)
    except RuntimeError as exc:  # e.g. missing GROQ_API_KEY
        raise HTTPException(500, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001  (LLM provider outage, rate limit, timeout)
        log.exception("RAG pipeline failed")
        raise HTTPException(502, f"LLM provider error: {type(exc).__name__}") from exc

    payload = {**result, "cached": False}
    set_cached(question, top_k, payload)
    payload["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return payload


# ---------- Frontend (local dev convenience; in K8s you may serve it from nginx instead) ----------
if settings.serve_frontend and FRONTEND_DIR.is_dir():

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")
