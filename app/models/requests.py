"""Pydantic request models with input validation."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.config import get_settings

settings = get_settings()


class ChatRequest(BaseModel):
    """A natural-language question for the RAG chatbot."""

    question: str = Field(
        min_length=1,
        max_length=settings.max_question_length,
        description="Natural-language question about HR policies.",
    )

    @field_validator("question")
    @classmethod
    def _question_not_blank(cls, value: str) -> str:
        value = value.strip().strip("?.").strip()
        if not value:
            raise ValueError("question must not be empty or contain only whitespace")
        return value


class DocumentIngestRequest(BaseModel):
    """Optional payload for the ingestion endpoint."""

    document_name: str | None = Field(
        default=None,
        description="Optional exact filename to ingest. Omitting indexes all documents.",
    )
    force: bool = Field(
        default=False,
        description="Re-index even if the file content is unchanged.",
    )

    @field_validator("document_name")
    @classmethod
    def _safe_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from pathlib import PurePosixPath

        # Strip any path components; only the bare filename is allowed.
        name = PurePosixPath(value.replace("\\", "/")).name
        if not name:
            raise ValueError("document_name must be a non-empty filename")
        return name


__all__ = ["ChatRequest", "DocumentIngestRequest"]