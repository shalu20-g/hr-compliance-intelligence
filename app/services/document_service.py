"""Document management service.

Bridges the ingestion pipeline with the API layer and provides the
document-list / delete operations used by the routes.

Safety model (defence in depth):

* Authorization is enforced in the API routes (HR-only ingestion).
* This service additionally validates every candidate file and runs the
  pending-review workflow: only validated HR documents or explicitly
  HR-approved documents reach the shared ChromaDB.
* Employee personal documents are analysed in-memory/temp files only and
  never written to the shared documents directory or ChromaDB.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.exceptions import (
    DocumentNotFoundError,
    IngestionError,
    UnsupportedFileTypeError,
)
from app.ingestion.loaders import VALID_EXTENSIONS, load_document
from app.ingestion.pipeline import IngestReport, ingest_documents
from app.ingestion.validator import extractive_summary, validate_upload
from app.rag.embeddings import get_embeddings
from app.rag.vectorstore import VectorStore
from app.services.review_store import ReviewStore

logger = logging.getLogger(__name__)


class DocumentService:
    """High-level operations over the document index."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._vectorstore: VectorStore | None = None
        self._documents_ready = False
        self._reviews: ReviewStore | None = None

    @property
    def reviews(self) -> ReviewStore:
        if self._reviews is None:
            self._reviews = ReviewStore(self.settings)
        return self._reviews

    @property
    def vectorstore(self) -> VectorStore:
        if self._vectorstore is None:
            self._vectorstore = VectorStore(self.settings, get_embeddings(self.settings))
        return self._vectorstore

    def list_documents(self) -> dict:
        """Return the indexed documents plus aggregate counts."""
        stores = self.vectorstore.list_documents()
        return {
            "documents": stores,
            "total_documents": len(stores),
            "total_chunks": self.vectorstore.count_chunks(),
        }

    def ingest(self, document_name: str | None = None, force: bool = False) -> IngestReport:
        """Run the ingestion pipeline through the shared vector store."""
        report = ingest_documents(
            settings=self.settings,
            vectorstore=self.vectorstore,
            force=force,
            filter_name=document_name,
        )
        if report.failures:
            # A partial failure is surfaced but not fatal if something was indexed.
            logger.warning("Ingestion finished with %d failure(s).", len(report.failures))
        return report

    def delete(self, document_name: str) -> int:
        """Remove a document and its vectors from the index."""
        name = Path(document_name).name  # sanitise: strip any path components
        indexed = {d["filename"] for d in self.vectorstore.list_documents()}
        if name not in indexed:
            raise DocumentNotFoundError(
                f"Document '{name}' is not present in the index."
            )
        deleted = self.vectorstore.delete_by_filename(name)
        logger.info("Removed document '%s' (%d chunks).", name, deleted)
        return deleted

    # ------------------------------------------------------------------ #
    # Validation + approval workflow (shared HR knowledge base)
    # ------------------------------------------------------------------ #
    def _extract_text_from_bytes(self, filename: str, content: bytes) -> str:
        """Extract text from raw bytes via a temp file (no Chroma writes)."""
        ext = Path(filename).suffix.lower()
        if ext not in VALID_EXTENSIONS:
            raise UnsupportedFileTypeError(
                f"Unsupported file type '{ext}'. Supported: "
                f"{', '.join(sorted(VALID_EXTENSIONS))}."
            )
        with tempfile.TemporaryDirectory(prefix="hr_validate_") as tmp:
            tmp_path = Path(tmp) / Path(filename).name
            tmp_path.write_bytes(content)
            try:
                pages = load_document(tmp_path)
            except UnsupportedFileTypeError:
                raise
            except Exception as exc:
                logger.warning("Text extraction failed for '%s': %s", filename, exc)
                return ""
        return "\n\n".join(p.page_content for p in pages)

    def submit_company_document(
        self, filename: str, content: bytes, uploaded_by: str
    ) -> dict[str, Any]:
        """Stage an HR company document for review (never auto-indexed).

        Always enters ``pending`` unless clearly personal/unrelated/unsafe,
        which enters ``rejected``. Both states keep the file quarantined under
        ``.pending`` so RAG answers are unaffected until explicit approval.
        """
        safe_name = Path(filename).name
        if safe_name != filename or not safe_name:
            raise IngestionError("Filenames must not contain path components.")
        ext = safe_name.lower().rsplit(".", 1)
        if len(ext) != 2 or f".{ext[1]}" not in VALID_EXTENSIONS:
            record = self.reviews.create(
                filename=safe_name,
                status="rejected",
                reason=f"Unsupported file type. Supported: .pdf, .docx, .txt.",
                category="unsupported_type",
                confidence=1.0,
                uploaded_by=uploaded_by,
            )
            return record
        if not content:
            return self.reviews.create(
                filename=safe_name,
                status="rejected",
                reason="Uploaded file is empty.",
                category="empty",
                confidence=1.0,
                uploaded_by=uploaded_by,
            )

        text = self._extract_text_from_bytes(safe_name, content)
        verdict = validate_upload(safe_name, content, text)
        # Safest design: even clearly-HR uploads start as pending; explicit
        # HR approval is what indexes them. Clear junk goes to rejected.
        status = "rejected" if verdict.verdict == "rejected" else "pending"
        self.reviews.save_pending_file(safe_name, content)
        return self.reviews.create(
            filename=safe_name,
            status=status,
            reason=verdict.reason,
            category=verdict.category,
            confidence=verdict.confidence,
            uploaded_by=uploaded_by,
        )

    def list_reviews(self, status: str | None = None) -> list[dict[str, Any]]:
        return self.reviews.list(status=status)

    def approve_review(self, review_id: str, approver: str) -> dict[str, Any]:
        """Approve a pending document: copy into shared dir and index it."""
        _ = approver
        record = self.reviews.get(review_id)
        if record is None:
            raise DocumentNotFoundError(
                f"Review '{review_id}' is not present in the pending queue."
            )
        if record.get("status") == "approved":
            return record
        filename = record["filename"]
        # Locate the quarantined file (handles de-duplicated suffixed names).
        candidates = sorted(self.reviews.pending_dir.glob(f"{Path(filename).stem}*"))
        src = next(
            (p for p in candidates if p.name == filename),
            self.reviews.pending_dir / filename,
        )
        if not src.exists():
            # Fall back: file may already have been placed in shared dir.
            src = Path(self.settings.documents_directory) / filename
        if not src.exists():
            raise DocumentNotFoundError(
                f"Quarantined file for '{filename}' is missing; cannot approve."
            )
        target = Path(self.settings.documents_directory) / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(src.read_bytes())
        # HR approval overrides heuristic classification: index exactly this file.
        report = ingest_documents(
            settings=self.settings,
            vectorstore=self.vectorstore,
            force=True,
            filter_name=filename,
        )
        if report.files_processed == 0 and report.failures:
            raise IngestionError(
                f"Approved file '{filename}' could not be indexed: "
                f"{report.failures[0].get('error')}"
            )
        updated = self.reviews.set_status(
            review_id,
            "approved",
            f"Approved by HR and indexed ({report.chunks_added} chunk(s)).",
        )
        return {**(updated or record), "chunks_added": report.chunks_added}

    def reject_review(
        self, review_id: str, approver: str, reason: str | None = None
    ) -> dict[str, Any]:
        """Reject/quarantine a document; ensure it is absent from ChromaDB."""
        _ = approver
        record = self.reviews.get(review_id)
        if record is None:
            raise DocumentNotFoundError(
                f"Review '{review_id}' is not present in the pending queue."
            )
        filename = record["filename"]
        try:
            if filename in {
                d["filename"] for d in self.vectorstore.list_documents()
            }:
                self.vectorstore.delete_by_filename(filename)
        except Exception:
            logger.exception("Failed to purge rejected file '%s' from Chroma.", filename)
        updated = self.reviews.set_status(
            review_id, "rejected", reason or record.get("reason", "Rejected by HR.")
        )
        return updated or record

    def ingest_validated_scan(
        self, document_name: str | None = None, force: bool = False
    ) -> IngestReport:
        """Validated folder scan: only clearly-HR files are indexed.

        Uncertain files become ``pending`` and personal/unrelated files become
        ``rejected``; neither is indexed, so RAG answers are unaffected.
        """
        from app.ingestion.pipeline import scan_documents

        candidates = scan_documents(
            self.settings.documents_directory, set(VALID_EXTENSIONS)
        )
        if document_name:
            candidates = [p for p in candidates if p.name == document_name]

        approved_names: list[str] = []
        skipped_pending = 0
        skipped_rejected = 0
        failures: list[dict] = []
        for path in candidates:
            try:
                content = path.read_bytes()
                text = self._extract_text_from_bytes(path.name, content)
                verdict = validate_upload(path.name, content, text)
            except Exception as exc:
                failures.append({"filename": path.name, "error": str(exc)})
                continue
            if verdict.verdict == "approved":
                approved_names.append(path.name)
            elif verdict.verdict == "rejected":
                skipped_rejected += 1
                # Quarantine record (dedupe: one record per filename).
                existing = [
                    r
                    for r in self.reviews.list()
                    if r["filename"] == path.name and r["status"] == "rejected"
                ]
                if not existing:
                    self.reviews.create(
                        filename=path.name,
                        status="rejected",
                        reason=verdict.reason,
                        category=verdict.category,
                        confidence=verdict.confidence,
                        uploaded_by="folder-scan",
                    )
                logger.info("Scan quarantined non-HR file '%s'.", path.name)
            else:
                skipped_pending += 1
                existing = [
                    r
                    for r in self.reviews.list()
                    if r["filename"] == path.name and r["status"] == "pending"
                ]
                if not existing:
                    self.reviews.create(
                        filename=path.name,
                        status="pending",
                        reason=verdict.reason,
                        category=verdict.category,
                        confidence=verdict.confidence,
                        uploaded_by="folder-scan",
                    )
                logger.info("Scan held uncertain file '%s' for review.", path.name)

        aggregate = IngestReport(files_found=len(candidates))
        aggregate.failures.extend(failures)
        for name in approved_names:
            sub = ingest_documents(
                settings=self.settings,
                vectorstore=self.vectorstore,
                force=force,
                filter_name=name,
            )
            aggregate.files_processed += sub.files_processed
            aggregate.files_skipped_unchanged += sub.files_skipped_unchanged
            aggregate.chunks_added += sub.chunks_added
            aggregate.chunks_skipped_duplicate += sub.chunks_skipped_duplicate
            aggregate.failures.extend(sub.failures)
            if sub.files_processed:
                existing = [
                    r
                    for r in self.reviews.list()
                    if r["filename"] == name and r["status"] == "approved"
                ]
                if not existing:
                    self.reviews.create(
                        filename=name,
                        status="approved",
                        reason="Validated as company HR/compliance during folder scan.",
                        category="hr_compliance",
                        confidence=0.8,
                        uploaded_by="folder-scan",
                    )
        logger.info(
            "Validated scan: %d approved/indexed, %d pending, %d rejected.",
            len(approved_names),
            skipped_pending,
            skipped_rejected,
        )
        return aggregate

    # ------------------------------------------------------------------ #
    # Employee personal documents (never touch shared ChromaDB)
    # ------------------------------------------------------------------ #
    def analyze_employee_document(
        self, filename: str, content: bytes, owner: str
    ) -> dict[str, Any]:
        """Summarise an employee's personal document without indexing it.

        The file is never written to the shared documents directory nor to
        ChromaDB. A Gemini summary is attempted when configured; otherwise a
        deterministic extractive summary is returned.
        """
        _ = owner
        safe_name = Path(filename).name
        if safe_name != filename or not safe_name:
            raise IngestionError("Filenames must not contain path components.")
        ext = Path(safe_name).suffix.lower()
        if ext not in VALID_EXTENSIONS:
            raise UnsupportedFileTypeError(
                f"Unsupported file type '{ext}'. Supported: "
                f"{', '.join(sorted(VALID_EXTENSIONS))}."
            )
        if not content:
            raise IngestionError("Uploaded file is empty.")
        text = self._extract_text_from_bytes(safe_name, content)
        if not text.strip():
            raise IngestionError("No extractable text found in the uploaded file.")

        summary = self._llm_or_extractive_summary(safe_name, text)
        return {
            "filename": safe_name,
            "summary": summary,
            "char_count": len(text),
            "indexed": False,
            "note": (
                "Personal document analysed separately; it was NOT added to "
                "the shared HR knowledge base and does not affect RAG answers."
            ),
        }

    def _llm_or_extractive_summary(self, filename: str, text: str) -> str:
        """Use Gemini for the summary when configured, else extractive."""
        if self.settings.llm_provider == "gemini" and self.settings.has_valid_api_key():
            try:
                from langchain_core.documents import Document as LCDocument

                from app.rag.chain import RagEngine
                from app.rag.prompt import build_summary_messages

                docs = [LCDocument(page_content=text[:8000], metadata={"section": "N/A"})]
                system, human = build_summary_messages(filename, docs)
                engine = RagEngine(self.settings)
                out = engine.llm(system, human)
                if isinstance(out, str) and out.strip():
                    return out.strip() + (
                        "\n\n_This summary is informational and does not "
                        "constitute legal advice._"
                    )
            except Exception:
                logger.exception("Gemini employee summary failed; using extractive fallback.")
        core = extractive_summary(text)
        return (
            f"Summary of personal document '{filename}' (offline extractive preview):\n\n"
            f"{core}\n\n_This summary is informational and does not constitute "
            f"legal advice. Personal documents are never added to the shared "
            f"HR knowledge base._"
        )

    def upload_to_documents_dir(self, filename: str, content: bytes) -> Path:
        """Persist an uploaded file into the documents directory (sanitised)."""
        safe_name = Path(filename).name
        if safe_name != filename:
            raise IngestionError("Filenames must not contain path components.")
        ext = Path(safe_name).suffix.lower()
        if ext not in VALID_EXTENSIONS:
            raise UnsupportedFileTypeError(
                f"Unsupported file type '{ext}'. Supported: "
                f"{', '.join(sorted(VALID_EXTENSIONS))}."
            )

        directory = Path(self.settings.documents_directory)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / safe_name
        target.write_bytes(content)
        logger.info("Saved uploaded file '%s' to %s.", safe_name, target)
        return target


__all__ = ["DocumentService"]