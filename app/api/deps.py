"""Shared FastAPI dependencies (overridable in tests)."""

from __future__ import annotations

from typing import Iterator

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_session
from app.rag.chain import RagEngine, get_rag_engine
from app.services.document_service import DocumentService


def get_document_service() -> DocumentService:
    """Factory for the document service used by the API routes."""
    return DocumentService(get_settings())


def get_db() -> Iterator[Session]:
    """Request-scoped users-database session (override in tests if needed)."""
    yield from get_session()


__all__ = ["get_rag_engine", "get_document_service", "get_db"]