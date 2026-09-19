"""Tests for document loading, chunking and the ingestion pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.chunker import chunk_document, finalise_chunk_ids
from app.ingestion.loaders import UnsupportedFileTypeError, load_document
from app.ingestion.pipeline import ingest_documents
from app.services.document_service import DocumentService
from tests.conftest import write_sample_documents


def _pdf_path(settings) -> Path:
    docs = write_sample_documents(settings, names=["employee_handbook.pdf"])
    return docs / "employee_handbook.pdf"


def _txt_path(settings) -> Path:
    docs = write_sample_documents(settings, names=["leave_policy.txt"])
    return docs / "leave_policy.txt"


def _docx_path(settings) -> Path:
    docs = write_sample_documents(settings, names=["employee_handbook.docx"])
    return docs / "employee_handbook.docx"


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #
def test_load_pdf_extracts_text_and_page_metadata(settings):
    pages = load_document(_pdf_path(settings))
    assert pages, "PDF should contain extractable text"
    assert pages[0].metadata["filename"] == "employee_handbook.pdf"
    assert pages[0].metadata["doc_type"] == "pdf"
    assert pages[0].metadata["page"] >= 1
    assert any("leave" in doc.page_content.lower() for doc in pages)


def test_load_txt_extracts_text(settings):
    docs = load_document(_txt_path(settings))
    assert len(docs) == 1
    assert "Annual Leave Policy" in docs[0].page_content
    assert docs[0].metadata["filename"] == "leave_policy.txt"
    assert docs[0].metadata["doc_type"] == "txt"


def test_load_docx_extracts_headings_and_tables(settings):
    docs = load_document(_docx_path(settings))
    assert docs, "DOCX should contain text"
    assert docs[0].metadata["doc_type"] == "docx"
    assert "Working Hours" in docs[0].page_content


def test_load_unsupported_extension_raises(settings):
    bogus = write_sample_documents(settings) / "notes.log"
    bogus.write_text("hello", encoding="utf-8")
    with pytest.raises(UnsupportedFileTypeError):
        load_document(bogus)


def test_load_nonexistent_file_raises(settings):
    with pytest.raises(Exception):
        load_document(Path(settings.documents_directory) / "missing.pdf")


# --------------------------------------------------------------------------- #
# Chunking
# --------------------------------------------------------------------------- #
def test_chunking_splits_and_preserves_metadata(settings):
    pages = load_document(_txt_path(settings))
    chunks = chunk_document(pages, settings)
    finalise_chunk_ids(chunks, "leave_policy.txt")

    assert len(chunks) > 1, "A long policy should be split into multiple chunks"
    for chunk in chunks:
        assert chunk.metadata["chunk_id"]
        assert chunk.metadata["chunk_hash"]
        assert chunk.metadata["section"]
        assert chunk.metadata["filename"] == "leave_policy.txt"
        assert isinstance(chunk.metadata["chunk_index"], int)


def test_chunking_respects_smaller_chunk_size(settings):
    pages = load_document(_txt_path(settings))
    baseline = len(chunk_document(pages, settings))

    big_settings = settings.model_copy(update={"chunk_size": 900, "chunk_overlap": 10})
    fewer_chunks = len(chunk_document(pages, big_settings))

    assert baseline > fewer_chunks


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
def test_ingest_indexes_documents(iso_settings):
    write_sample_documents(iso_settings)
    report = ingest_documents(settings=iso_settings)

    assert report.files_found >= 3
    assert report.files_processed == report.files_found
    assert report.failures == []
    assert report.chunks_added > 0

    service = DocumentService(iso_settings)
    names = {d["filename"] for d in service.list_documents()["documents"]}
    assert "leave_policy.txt" in names
    assert "employee_handbook.pdf" in names
    assert "employee_handbook.docx" in names


def test_reingestion_skips_unchanged(iso_settings):
    write_sample_documents(iso_settings)
    first = ingest_documents(settings=iso_settings)
    second = ingest_documents(settings=iso_settings)

    assert second.files_skipped_unchanged == first.files_processed
    assert second.chunks_added == 0

    service = DocumentService(iso_settings)
    assert service.list_documents()["total_chunks"] == first.chunks_added


def test_modified_file_is_reindexed(iso_settings):
    write_sample_documents(iso_settings)
    first = ingest_documents(settings=iso_settings)

    policy = Path(iso_settings.documents_directory) / "leave_policy.txt"
    original = policy.read_text(encoding="utf-8")
    policy.write_text(
        original + "\n9. Renewed Leave\nLeave entitlements are renewed every January.\n",
        encoding="utf-8",
    )

    second = ingest_documents(settings=iso_settings)
    assert second.files_processed == 1  # only the modified file
    assert second.files_skipped_unchanged == first.files_processed - 1
    assert second.chunks_added > 0, "Modified content must produce new chunks"


def test_force_reindex_readds_identical_content(iso_settings):
    write_sample_documents(iso_settings)
    ingest_documents(settings=iso_settings)

    report = ingest_documents(settings=iso_settings, force=True)
    assert report.files_processed == report.files_found
    assert report.chunks_added > 0, "Force re-index must re-add chunks after deletion"

    service = DocumentService(iso_settings)
    assert service.list_documents()["total_chunks"] > 0


def test_delete_document(iso_settings):
    write_sample_documents(iso_settings)
    ingest_documents(settings=iso_settings)
    service = DocumentService(iso_settings)

    before = {d["filename"] for d in service.list_documents()["documents"]}
    assert "leave_policy.txt" in before

    removed = service.delete("leave_policy.txt")
    assert removed > 0

    after = {d["filename"] for d in service.list_documents()["documents"]}
    assert "leave_policy.txt" not in after


def test_delete_missing_document_raises(iso_settings):
    service = DocumentService(iso_settings)
    with pytest.raises(Exception):
        service.delete("does_not_exist.txt")


def test_empty_documents_directory_is_not_an_error(iso_settings):
    empty_settings = iso_settings.model_copy(
        update={"documents_directory": str(Path(iso_settings.documents_directory) / "empty")}
    )
    report = ingest_documents(settings=empty_settings)
    assert report.files_found == 0
    assert report.failures == []
    assert report.chunks_added == 0


def test_ingest_respects_filter_name(iso_settings):
    write_sample_documents(iso_settings)
    report = ingest_documents(settings=iso_settings, filter_name="leave_policy.txt")
    assert report.files_processed == 1
    assert report.files_found == 1

    service = DocumentService(iso_settings)
    names = {d["filename"] for d in service.list_documents()["documents"]}
    assert names == {"leave_policy.txt"}