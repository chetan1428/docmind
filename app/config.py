"""All configuration comes from environment variables (12-factor style).

This is deliberate: in Docker you pass them with -e / env_file, in Kubernetes
with ConfigMaps + Secrets, in AWS with Parameter Store / Secrets Manager.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

from app import __version__


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "DocMind"
    # CI can inject the git SHA here so /health shows exactly what is deployed
    app_version: str = __version__
    log_level: str = "INFO"

    # --- Infrastructure ---
    database_url: str = "postgresql+psycopg://docmind:docmind@localhost:5432/docmind"
    redis_url: str = "redis://localhost:6379/0"

    # --- AI providers ---
    # "hash"  -> free, offline embeddings (good for learning deployment, no API key)
    # "openai"-> any OpenAI-compatible API (OpenAI, Groq, Together, Ollama, vLLM...)
    embedding_provider: str = "hash"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 384

    # "groq"       -> LangGraph agentic RAG with a Groq-hosted LLM (needs GROQ_API_KEY)
    # "extractive" -> no LLM, picks the best sentences from retrieved chunks (offline)
    llm_provider: str = "groq"
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"  # writes the final answer
    groq_fast_model: str = "openai/gpt-oss-20b"  # grades documents + rewrites queries
    llm_temperature: float = 0.1
    max_query_rewrites: int = 1

    # Only used when EMBEDDING_PROVIDER=openai (Groq has no embeddings API)
    openai_api_key: str | None = None
    openai_base_url: str | None = None

    # --- RAG tuning ---
    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k: int = 4

    # --- Misc ---
    cache_ttl_seconds: int = 3600
    max_upload_mb: int = 5
    serve_frontend: bool = True
    cors_origins: str = "*"


settings = Settings()
