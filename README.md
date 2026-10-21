# DocMind: Agentic RAG Document Q&A

Upload documents (`.txt`, `.md`, `.pdf`), then ask questions about them. A **LangGraph** pipeline running on a **Groq** LLM grades what it retrieves, rewrites the search if nothing useful came back, and answers with cited sources.

The application code is complete and tested. **The deployment is yours to build**: Docker, Compose, Kubernetes, CI/CD and AWS. See [`DEVOPS-TASKS.md`](DEVOPS-TASKS.md).

## Architecture

```
                 ┌──────────────┐
  Browser ──────▶│   API        │  FastAPI  (uvicorn, port 8000)
                 │ app.main     │  /api/documents  /api/ask  /health  /ready  /metrics
                 └──┬───────┬───┘
         enqueue job│       │ SQL + vector search
                    ▼       ▼
             ┌────────┐  ┌──────────────────────┐
             │ Redis  │  │ Postgres + pgvector  │  documents, chunks(embedding vector(384))
             │ queue  │  └──────────────────────┘
             │ +cache │          ▲
             └───┬────┘          │ store chunks + embeddings
                 ▼               │
             ┌───────────────────┴──┐
             │  Worker  app.worker  │  chunk (LangChain splitter) → embed → store (RQ)
             └──────────────────────┘
```

### The LangGraph pipeline (`app/rag_graph.py`)

```
START → retrieve → grade ─┬─ relevant passages found ─────────▶ generate ──▶ END
                          ├─ none relevant, rewrites left ────▶ rewrite ──▶ retrieve
                          └─ nothing found ───────────────────▶ no_answer ─▶ END
```

| Node | What it does | Model |
|---|---|---|
| `retrieve` | pgvector cosine search, top-k chunks | none |
| `grade` | keeps only passages that actually help answer the question | `GROQ_FAST_MODEL` |
| `rewrite` | turns the question into a better search query (max `MAX_QUERY_REWRITES`) | `GROQ_FAST_MODEL` |
| `generate` | writes the cited answer from the relevant passages | `GROQ_MODEL` |
| `no_answer` | honest "not found" instead of a hallucination | none |

`/api/ask` returns the `steps` the graph took (e.g. `retrieve → grade → rewrite → retrieve → grade → generate`) and the final `search_query`; the UI shows both.

**Four processes, two of which you build from the same image:**

| Component | Command | Stateful? | Port |
|---|---|---|---|
| API | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | no | 8000 |
| Worker | `python -m app.worker` | no | none |
| Postgres + pgvector | the `pgvector/pgvector:pg16` image, or AWS RDS | **yes** | 5432 |
| Redis | the `redis:7` image, or AWS ElastiCache | cache only | 6379 |

The frontend (`frontend/index.html`) is served by the API at `/` by default. For an extra exercise, set `SERVE_FRONTEND=false` and serve it from nginx instead. It uses relative URLs, so routing `/api` to the backend just works.

## AI modes

| Mode | Settings | Needs |
|---|---|---|
| **Groq + LangGraph** (default) | `LLM_PROVIDER=groq`, `GROQ_API_KEY=...` | a free key from console.groq.com |
| **Offline** | `LLM_PROVIDER=extractive` | nothing; same graph, no LLM (extractive answers) |

**Embeddings:** Groq doesn't offer an embeddings API, so the default `EMBEDDING_PROVIDER=hash` is a free offline embedder (keyword-based). For real semantic search, set `EMBEDDING_PROVIDER=openai` with any OpenAI-compatible embeddings endpoint, then re-upload your documents.

Groq model IDs change: check console.groq.com/docs/models and update `GROQ_MODEL` / `GROQ_FAST_MODEL` if one is deprecated. Doing that **without rebuilding the image** (only a ConfigMap change) is a good DevOps exercise.

The API starts fine without `GROQ_API_KEY` (health checks pass), but `/api/ask` returns 500 until the key is set. Managing it as a proper **Secret** is part of your deployment work.

## Configuration (environment variables)

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://docmind:docmind@localhost:5432/docmind` | **secret** (has a password) |
| `REDIS_URL` | `redis://localhost:6379/0` | |
| `APP_VERSION` | `0.1.0` | set this to the git SHA in CI; shown on `/health` |
| `LLM_PROVIDER` | `groq` | `groq` or `extractive` |
| `GROQ_API_KEY` | none | **secret** |
| `GROQ_MODEL` / `GROQ_FAST_MODEL` | `openai/gpt-oss-120b` / `openai/gpt-oss-20b` | answer model / grade+rewrite model |
| `MAX_QUERY_REWRITES` | `1` | LangGraph rewrite loop limit |
| `LLM_TEMPERATURE` | `0.1` | |
| `EMBEDDING_PROVIDER` | `hash` | `hash` or `openai` |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `EMBEDDING_MODEL` | none | only for `EMBEDDING_PROVIDER=openai`; key is a **secret** |
| `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` | none | optional LangSmith tracing of every graph run |
| `EMBEDDING_DIM` | `384` | vector column size; changing it needs a fresh DB |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` / `TOP_K` | `800` / `120` / `4` | RAG tuning |
| `CACHE_TTL_SECONDS` | `3600` | |
| `MAX_UPLOAD_MB` | `5` | |
| `SERVE_FRONTEND` | `true` | |
| `CORS_ORIGINS` | `*` | comma-separated |
| `LOG_LEVEL` | `INFO` | |

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | **Liveness**: process is up (no dependency checks) |
| `GET` | `/ready` | **Readiness**: Postgres + Redis reachable, otherwise 503 |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/docs` | Swagger UI |
| `POST` | `/api/documents` | multipart upload (`file`); returns 202, ingestion is async |
| `GET` | `/api/documents`, `/api/documents/{id}` | list / status |
| `DELETE` | `/api/documents/{id}` | delete |
| `POST` | `/api/ask` | `{"question": "...", "top_k": 4}` returns answer, sources, steps, search_query, cached flag, latency |

## Run locally without Docker (to see it work first)

You need Postgres with the pgvector extension, and Redis, running locally.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env

uvicorn app.main:app --reload --port 8000   # terminal 1
python -m app.worker                        # terminal 2
# open http://localhost:8000 and upload samples/kubernetes-basics.md
```

Tables and the `vector` extension are created automatically on startup. The DB user needs permission to run `CREATE EXTENSION`.

## Tests and lint

```bash
ruff check . && ruff format --check .
pytest -q          # unit + LangGraph tests (fake LLMs); no Postgres, Redis or Groq key needed
```

## Layout

```
app/
  main.py        API routes, health and readiness, metrics
  worker.py      background worker entrypoint
  tasks.py       ingestion job (chunk → embed → store)
  db.py          SQLAlchemy models, pgvector HNSW index, init with retries
  cache.py       Redis answer cache + queue connection
  rag_graph.py   LangGraph agentic RAG (retrieve → grade → rewrite → generate)
  llm.py         Groq models (langchain-groq), prompts, offline fallback
  retrieval.py   pgvector similarity search
  embeddings.py  hash / OpenAI-compatible embeddings
  chunking.py    text extraction + LangChain text splitter
  config.py      all settings from env vars
frontend/index.html
samples/         a doc to test with
tests/
```

## Run with Docker Compose

```bash
cp .env.example .env    # add your GROQ_API_KEY
docker compose up -d --build
open http://localhost:8000
docker compose down     # keeps data; add -v to wipe it
```

Prebuilt multi-arch image: `docker pull chetansatkar45/docmind:latest`
