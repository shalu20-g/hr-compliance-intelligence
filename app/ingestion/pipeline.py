"""Document ingestion pipeline.

Scans ``data/documents/``, loads each supported file, chunks it, embeds the
chunks and stores them in the persistent ChromaDB collection.

De-duplication strategy:

* Every chunk has a content-based id ``{filename}::{sha256(text)}``.
* The pipeline first computes a whole-file content hash (``doc_hash``).
  - If a file was already indexed with the same hash, it is skipped entirely.
  - If the file changed (or ``force=True``), its old vectors are deleted and
    the new chunks are indexed.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings, get_settings
from app.ingestion.chunker import chunk_document, finalise_chunk_ids
from app.ingestion.loaders import VALID_EXTENSIONS, load_document
from app.rag.vectorstore import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class IngestReport:
    """Summary of one ingestion run."""

    files_found: int = 0
    files_processed: int = 0
    files_skipped_unchanged: int = 0
    chunks_added: int = 0
    chunks_skipped_duplicate: int = 0
    failures: list[dict] = field(default_factory=list)


def _file_hash(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            sha.update(block)
    return sha.hexdigest()


def scan_documents(
    documents_directory: str, extensions: set[str]
) -> list[Path]:
    """Return supported document paths sorted for deterministic ordering."""
    root = Path(documents_directory)
    if not root.exists():
        logger.warning("Documents directory '%s' does not exist yet.", root)
        return []
    return sorted(
        p for p in root.iterdir()
        if p.is_file() and p.suffix.lower() in extensions
    )


def ingest_documents(
    settings: Settings | None = None,
    vectorstore: VectorStore | None = None,
    force: bool = False,
    filter_name: str | None = None,
) -> IngestReport:
    """Index every supported file in the documents directory.

    Args:
        settings: app settings (defaults to the global cached settings).
        vectorstore: optional pre-built store (used by tests / service layer).
        force: re-index documents even if their content hash is unchanged.
        filter_name: only ingest the file with this exact name.
    """
    settings = settings or get_settings()
    report = IngestReport()

    files = scan_documents(settings.documents_directory, set(VALID_EXTENSIONS))
    if filter_name:
        files = [p for p in files if p.name == filter_name]
    report.files_found = len(files)

    if vectorstore is None:
        from app.rag.embeddings import get_embeddings

        # NOTE: vectorstore init may raise ConfigurationError when the Gemini
        # key is missing and the provider is 'gemini'.
        vectorstore = VectorStore(settings, get_embeddings(settings))

    existing_hashes = vectorstore.document_hashes()
    existing_ids = vectorstore.existing_ids()

    for path in files:
        try:
            doc_hash = _file_hash(path)

            if force:
                deleted = vectorstore.delete_by_filename(path.name)
                if deleted or path.name in existing_hashes:
                    logger.info("[force] Re-indexing document '%s'.", path.name)
                # Refresh the known-id set so identical chunks can be re-added.
                existing_ids = vectorstore.existing_ids()
            elif existing_hashes.get(path.name) == doc_hash:
                report.files_skipped_unchanged += 1
                logger.info("Skipping unchanged document '%s'.", path.name)
                continue

            pages = load_document(path)
            chunks = chunk_document(pages, settings)
            chunks = finalise_chunk_ids(chunks, path.name)

            # Skip chunks already present in the store.
            additions = [
                c for c in chunks if c.metadata["chunk_id"] not in existing_ids
            ]
            dups = len(chunks) - len(additions)
            report.chunks_skipped_duplicate += dups

            # Attach file-level identity + a stable ingested_at timestamp.
            timestamp = datetime.now(timezone.utc).isoformat()
            for chunk in additions:
                chunk.metadata = {
                    **chunk.metadata,
                    "doc_hash": doc_hash,
                    "ingested_at": timestamp,
                }

            if additions:
                vectorstore.add_documents(additions)
                existing_ids.update(c.metadata["chunk_id"] for c in additions)

            report.chunks_added += len(additions)
            report.files_processed += 1
            logger.info(
                "Indexed '%s': %d chunk(s) added, %d duplicate(s).",
                path.name,
                len(additions),
                dups,
            )
        except Exception as exc:  # per-file isolation
            report.failures.append(
                {"filename": path.name, "error": str(exc)}
            )
            logger.exception("Failed to ingest '%s'.", path.name)

    if report.failures:
        logger.warning(
            "Ingestion finished with %d failure(s).", len(report.failures)
        )
    else:
        logger.info(
            "Ingestion complete: %d processed, %d unchanged, %d chunks added.",
            report.files_processed,
            report.files_skipped_unchanged,
            report.chunks_added,
        )
    return report


__all__ = ["ingest_documents", "IngestReport", "scan_documents"]