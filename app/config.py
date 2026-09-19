"""Application configuration loaded from environment variables.

All settings are read from the process environment and/or a local ``.env``
file (see ``.env.example``). No secrets are hardcoded here.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.exceptions import ConfigurationError


class Settings(BaseSettings):
    """Central application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "Enterprise HR Compliance Bot"
    app_version: str = "1.0.0"
    log_level: str = "INFO"

    # --- Google Gemini ---
    google_api_key: str | None = Field(default=None, repr=False)
    gemini_model: str = "gemini-2.0-flash"
    embedding_model: str = "models/text-embedding-004"
    embeddings_provider: Literal["gemini", "dummy"] = "gemini"
    llm_provider: Literal["gemini", "dummy"] = "gemini"

    # --- LLM reliability ---
    # Bounded retries for transient Gemini failures (rate limits, timeouts,
    # temporary 5xx/service errors). Non-transient errors are never retried.
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_timeout_seconds: float = Field(default=60.0, gt=0)
    llm_retry_backoff_seconds: float = Field(default=1.5, ge=0.0)

    # --- Storage ---
    chroma_persist_directory: str = "data/chroma_db"
    chroma_collection_name: str = "hr_compliance_docs"
    documents_directory: str = "data/documents"

    # --- Retrieval ---
    top_k: int = Field(default=5, ge=1, le=50)
    similarity_threshold: float = Field(default=0.55, ge=0.0, le=1.0)

    # --- Chunking / ingestion ---
    chunk_size: int = Field(default=1000, ge=100, le=10000)
    chunk_overlap: int = Field(default=150, ge=0, le=2000)
    allowed_extensions: list[str] = [".pdf", ".docx", ".txt"]

    # --- Request validation ---
    max_question_length: int = Field(default=500, ge=1, le=5000)
    max_upload_size_mb: int = Field(default=50, ge=1, le=500)

    # --- Users database (PostgreSQL in production, SQLite file for dev) ---
    # Examples:
    #   PostgreSQL: postgresql://hrbot:secret@localhost:5432/hrbot
    #   SQLite dev: sqlite:///./data/app.db
    database_url: str = Field(default="sqlite:///./data/app.db")

    # --- JWT authentication ---
    # MUST be overridden in production via JWT_SECRET_KEY env var.
    jwt_secret_key: str = Field(default="dev-only-secret-key-change-me")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=480, ge=5, le=10080)

    def has_valid_api_key(self) -> bool:
        """True when a real (non-placeholder) Gemini key is configured."""
        return bool(self.google_api_key and self.google_api_key != "your_api_key_here")

    def require_api_key(self) -> str:
        """Return the Gemini API key or raise a clear configuration error."""
        if not self.has_valid_api_key():
            raise ConfigurationError(
                "GOOGLE_API_KEY is not configured. Set it in your environment or "
                ".env file (see .env.example). For offline development/test mode "
                "set EMBEDDINGS_PROVIDER=dummy and LLM_PROVIDER=dummy."
            )
        return self.google_api_key


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    return Settings()