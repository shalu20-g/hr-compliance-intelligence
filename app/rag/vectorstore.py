"""ChromaDB vector store wrapper.

The store persists locally under ``settings.chroma_persist_directory`` and is
reused across API restarts (it is *not* rebuilt on startup).

Chunk identifiers are deterministic: ``{filename}::{content_hash}``, which
lets the ingestion pipeline skip already-indexed chunks and overwrite chunks
for documents that have changed.
"""

from __future__ import annotations

import logging

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.config import Settings
from app.exceptions import VectorStoreError

logger = logging.getLogger(__name__)

try:
    import chromadb
    from langchain_chroma import Chroma
except ImportError as exc:  # pragma: no cover - environment issue
    raise VectorStoreError(
        "ChromaDB dependencies are missing. Run `pip install -r requirements.txt`."
    ) from exc


class VectorStore:
    """Thin wrapper around a persistent Chroma collection."""

    def __init__(self, settings: Settings, embeddings: Embeddings) -> None:
        self._embeddings = embeddings
        try:
            self._client = chromadb.PersistentClient(
                path=settings.chroma_persist_directory
            )
            self._collection = self._client.get_or_create_collection(
                name=settings.chroma_collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            self._store = Chroma(
                client=self._client,
                collection_name=settings.chroma_collection_name,
                embedding_function=embeddings,
            )
        except Exception as exc:  # e.g. corrupted DB / permission issues
            logger.exception("Failed to initialise ChromaDB at %s", settings.chroma_persist_directory)
            raise VectorStoreError(
                f"Could not open the vector database at "
                f"'{settings.chroma_persist_directory}'."
            ) from exc
        logger.info(
            "Vector store ready: collection=%s persistent_path=%s",
            settings.chroma_collection_name,
            settings.chroma_persist_directory,
        )

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    def add_documents(self, documents: list[Document]) -> int:
        """Insert documents into ChromaDB. Returns the number inserted."""
        if not documents:
            return 0
        ids = [doc.metadata.get("chunk_id") for doc in documents]
        if not all(ids):
            raise VectorStoreError("All inserted chunks must have a 'chunk_id'.")
        ids = [str(i) for i in ids]
        self._store.add_documents(documents, ids=ids)
        logger.info("Added %d chunk vector(s) to ChromaDB.", len(documents))
        return len(documents)

    def delete_by_filename(self, filename: str) -> int:
        """Delete all chunks belonging to a document. Returns number deleted."""
        existing = self._collection.get(where={"filename": filename})
        ids = existing.get("ids", [])
        if ids:
            self._collection.delete(ids=ids)
            logger.info("Deleted %d chunk(s) for document '%s'.", len(ids), filename)
        return len(ids)

    def existing_ids(self) -> set[str]:
        """Return all chunk ids currently stored (used for dedup)."""
        result = self._collection.get(include=[])
        return set(result.get("ids", []))

    def document_hashes(self) -> dict[str, str]:
        """Map every indexed filename to its stored content hash."""
        result = self._collection.get(include=["metadatas"])
        hashes: dict[str, str] = {}
        for meta in result.get("metadatas", []):
            filename = meta.get("filename")
            doc_hash = meta.get("doc_hash")
            if filename and doc_hash:
                hashes[filename] = doc_hash
        return hashes

    def get_document_chunks(self, filename: str) -> list[Document]:
        """Return the stored chunks for one document, ordered by chunk index."""
        result = self._collection.get(
            where={"filename": filename},
            include=["documents", "metadatas"],
        )
        contents = result.get("documents", []) or []
        metadatas = result.get("metadatas", []) or []
        documents = []
        for content, metadata in zip(contents, metadatas):
            documents.append(Document(page_content=content, metadata=metadata))
        documents.sort(
            key=lambda doc: (
                doc.metadata.get("chunk_index") is None,
                doc.metadata.get("chunk_index") or 0,
            )
        )
        return documents

    def list_documents(self) -> list[dict]:
        """Return one entry per indexed document with chunk counts."""
        result = self._collection.get(include=["metadatas"])
        counts: dict[str, int] = {}
        ingested: dict[str, str] = {}
        for meta in result.get("metadatas", []):
            filename = meta.get("filename")
            if not filename:
                continue
            counts[filename] = counts.get(filename, 0) + 1
            when = meta.get("ingested_at")
            if when and (filename not in ingested or when > ingested[filename]):
                ingested[filename] = when
        return [
            {
                "filename": name,
                "chunk_count": counts[name],
                "ingested_at": ingested.get(name),
            }
            for name in counts
        ]

    def count_chunks(self) -> int:
        """Total number of stored chunks."""
        return len(self._collection.get(include=[])["ids"])

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    def search(self, query: str, k: int) -> tuple[list[Document], list[float]]:
        """Return the top-``k`` chunks and their relevance scores."""
        try:
            results = self._store.similarity_search_with_relevance_scores(query, k=k)
            documents = [doc for doc, _score in results]
            scores = [float(score) for _doc, score in results]
            return documents, scores
        except Exception as exc:
            logger.exception("ChromaDB similarity search failed.")
            raise VectorStoreError("The vector database failed during retrieval.") from exc


def chunk_id_for(filename: str, content_hash: str) -> str:
    """Deterministic, de-duplicatable Chroma id for a chunk."""
    return f"{filename}::{content_hash}"


__all__ = ["VectorStore", "chunk_id_for"]