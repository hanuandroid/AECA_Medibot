"""Application settings, loaded from environment variables / backend/.env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Data -----------------------------------------------------------------------------
    data_dir: Path = REPO_ROOT / "mediassist_data"
    sqlite_path: Path = REPO_ROOT / "mediassist_data" / "db" / "mediassist.db"
    # Relative dates in analytical questions ("last month") are resolved against this date.
    # Empty -> the latest date present in the database (the dataset covers 2024 only).
    sql_as_of_date: str = ""
    sql_max_rows: int = 200

    # --- Qdrant ---------------------------------------------------------------------------
    # QDRANT_URL wins; otherwise QDRANT_PATH selects Qdrant's embedded (local) engine.
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_path: str | None = None
    qdrant_collection: str = "medibot_chunks"

    # --- Models ---------------------------------------------------------------------------
    dense_model: str = "BAAI/bge-small-en-v1.5"
    sparse_model: str = "Qdrant/bm25"
    reranker_model: str = "jinaai/jina-reranker-v1-turbo-en"
    chunk_max_tokens: int = 384
    models_cache_dir: Path = BACKEND_DIR / ".cache" / "models"

    # --- Retrieval ------------------------------------------------------------------------
    retrieval_candidates: int = 10  # hybrid (fused) candidate set passed to the reranker
    prefetch_limit: int = 30  # per-branch (dense / sparse) candidates before fusion
    rerank_top_k: int = 3  # chunks that reach the LLM

    # --- LLM ------------------------------------------------------------------------------
    # "openai" = any OpenAI-compatible endpoint (OpenAI, Groq, OpenRouter, Gemini, Together…)
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    groq_api_key: str | None = None
    llm_temperature: float = 0.0
    llm_timeout_seconds: float = 60.0

    # --- Auth -----------------------------------------------------------------------------
    jwt_secret: str = Field(default="", repr=False)
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 480
    # Demo users "username:role:password" separated by ";" (development only).
    demo_users: str = Field(default="", repr=False)
    # Shared demo password used when DEMO_USERS is empty.
    demo_password: str = Field(default="", repr=False)

    # --- API ------------------------------------------------------------------------------
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    warmup_models: bool = True

    @property
    def resolved_llm_api_key(self) -> str | None:
        if self.llm_api_key:
            return self.llm_api_key
        if self.llm_provider == "anthropic":
            return self.anthropic_api_key
        if self.llm_provider == "groq":
            return self.groq_api_key
        return self.openai_api_key

    @property
    def llm_configured(self) -> bool:
        return bool(self.resolved_llm_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
