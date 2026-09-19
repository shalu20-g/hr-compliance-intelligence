"""Chunking of loaded documents using a LangChain text splitter."""

from __future__ import annotations

import hashlib
import logging

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from app.config import Settings
from app.ingestion.loaders import _detect_section, normalize_metadata
from app.rag.vectorstore import chunk_id_for

logger = logging.getLogger(__name__)


def _content_hash(text: str) -> str:
    """SHA-256 of the chunk text, used for stable, de-duplicatable ids."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_document(pages: list[Document], settings: Settings) -> list[Document]:
    """Split source documents into overlapping chunks with rich metadata.

    Each page-level document is split independently so the ``page`` metadata
    stays accurate. Every output chunk receives:
      - ``chunk_index`` / ``chunk_total``  (position within the file)
      - ``chunk_id``                       (deterministic id for dedup)
      - ``section``                        (heading-like section, if found)
      - ``chunk_hash``                     (content hash)
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator=True,
        length_function=len,
    )

    chunks: list[Document] = []
    for page in pages:
        page_chunks = splitter.split_documents([page])
        base = normalize_metadata(page.metadata)

        for index, chunk in enumerate(page_chunks):
            text = chunk.page_content.strip()
            if not text:
                continue

            section = _detect_section(text) or base.get("section")
            chunk_hash = _content_hash(text)
            metadata = dict(base)
            metadata.update(
                {
                    "chunk_hash": chunk_hash,
                    "section": section,
                    "chunk_index": len(chunks),
                    "chunk_total": None,  # filled in by pipeline at file level
                }
            )
            chunks.append(
                Document(page_content=text, metadata=metadata)
            )

    logger.info("Split into %d chunk(s).", len(chunks))
    return chunks


def finalise_chunk_ids(
    chunks: list[Document], filename: str
) -> list[Document]:
    """Assign deterministic chunk ids and total counts for a single file."""
    total = len(chunks)
    for index, chunk in enumerate(chunks):
        metadata = dict(chunk.metadata)
        metadata["chunk_index"] = index
        metadata["chunk_total"] = total
        metadata["chunk_id"] = chunk_id_for(
            filename, str(metadata.get("chunk_hash"))
        )
        chunk.metadata = metadata
    return chunks


__all__ = ["chunk_document", "finalise_chunk_ids"]