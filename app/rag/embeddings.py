"""Embedding providers for the RAG pipeline.

Two providers are supported:

* ``gemini``  - Google Generative AI embeddings (production).
* ``dummy``   - deterministic, hash-based embeddings for offline development
                and automated tests. NOT suitable for production search
                quality; it exists so the whole pipeline can run without a
                Gemini API key.
"""

from __future__ import annotations

import hashlib
import logging

from langchain_core.embeddings import Embeddings
from pydantic import BaseModel

from app.config import Settings
from app.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class DummyEmbeddings(BaseModel, Embeddings):
    """Deterministic, hash-based embeddings used only for offline dev/testing.

    Vectors derive from a SHA-256 of the text, so identical text always maps
    to the same vector and near-identical text gets reasonably close vectors.
    """

    dimension: int = 768

    def _embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [
            ((digest[i % 32] + ((i * 7 + 13) & 0xFF)) % 256) / 255.0
            for i in range(self.dimension)
        ]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def get_embeddings(settings: Settings) -> Embeddings:
    """Build the configured embeddings provider (lazy, cached by caller)."""
    if settings.embeddings_provider == "dummy":
        logger.warning("Using DummyEmbeddings mock provider (offline/dev mode only).")
        return DummyEmbeddings()

    # Production path: real Gemini embeddings.
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
    except ImportError as exc:  # pragma: no cover - environment issue
        raise ConfigurationError(
            "langchain-google-genai is not installed. Run `pip install -r requirements.txt`."
        ) from exc

    api_key = settings.require_api_key()
    logger.info("Creating GoogleGenerativeAIEmbeddings (model=%s)", settings.embedding_model)
    return GoogleGenerativeAIEmbeddings(
        model=settings.embedding_model,
        google_api_key=api_key,
        task_type="retrieval_document",
    )