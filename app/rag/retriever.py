"""Retrieval layer: query the vector store and apply relevance filtering."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.rag.vectorstore import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A single retrieved context chunk with metadata and score."""

    content: str
    metadata: dict
    score: float

    @property
    def document(self) -> str:
        return str(self.metadata.get("filename", "unknown"))

    @property
    def page(self) -> str:
        return self.metadata.get("page", "")

    @property
    def section(self) -> str:
        return str(self.metadata.get("section") or "General")

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "metadata": {
                k: v
                for k, v in self.metadata.items()
                if k not in {"content", "source"}  # no absolute paths
            },
            "score": round(self.score, 4),
        }


def retrieve(
    vectorstore: VectorStore,
    question: str,
    top_k: int,
    threshold: float,
) -> list[RetrievedChunk]:
    """Retrieve the top-``top_k`` chunks and keep those above ``threshold``.

    Scores returned by ``similarity_search_with_relevance_scores`` are cosine
    similarities in ``(0, 1]`` (1.0 = identical). Chunks scored below the
    configured threshold are dropped so the bot only grounds its answer on
    genuinely relevant context.
    """
    documents, scores = vectorstore.search(question, k=top_k)

    chunks: list[RetrievedChunk] = []
    for doc, score in zip(documents, scores):
        chunk = RetrievedChunk(
            content=doc.page_content,
            metadata=dict(doc.metadata),
            score=float(score),
        )
        if float(score) >= threshold:
            chunks.append(chunk)

    logger.info(
        "Retrieved %d chunk(s) for question (kept %d above threshold %.2f).",
        len(documents),
        len(chunks),
        threshold,
    )

    # Deterministic ordering: best match first.
    chunks.sort(key=lambda c: c.score, reverse=True)
    return chunks


@dataclass
class SourceReference:
    """A de-duplicated human-readable source for an answer."""

    document: str
    page: str = ""
    section: str = "General"
    relevance_score: float = 0.0

    @classmethod
    def from_chunk(cls, chunk: RetrievedChunk) -> "SourceReference":
        # Clamp to [0, 1]: Chroma relevance scores can drift slightly outside
        # due to floating-point/normalisation quirks, and the API response
        # model rejects out-of-range values (which previously surfaced as 500).
        score = round(max(0.0, min(1.0, float(chunk.score))), 4)
        return cls(
            document=chunk.document,
            page=str(chunk.page),
            section=chunk.section,
            relevance_score=score,
        )

    def key(self) -> tuple[str, str, str]:
        return (self.document, self.page, self.section)

    def to_dict(self) -> dict:
        return {
            "document": self.document,
            "page": self.page if self.page else None,
            "section": self.section,
            "relevance_score": self.relevance_score,
        }


def dedupe_sources(chunks: list[RetrievedChunk]) -> list[SourceReference]:
    """Collapse retrieved chunks into unique (document, page, section) refs."""
    best: dict[tuple[str, str, str], SourceReference] = {}
    for chunk in chunks:
        ref = SourceReference.from_chunk(chunk)
        key = ref.key()
        if key not in best or ref.relevance_score > best[key].relevance_score:
            best[key] = ref
    return sorted(best.values(), key=lambda r: r.relevance_score, reverse=True)


__all__ = ["RetrievedChunk", "SourceReference", "retrieve", "dedupe_sources"]