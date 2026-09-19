"""Document management endpoints: ingest, list, upload, delete, review.

Authorization: company-policy ingestion endpoints require HR/Admin
(``require_hr_admin`` resolves the role server-side; employees get 403).
Validation: every candidate file is validated before it can reach the shared
ChromaDB; uncertain files enter Pending Review and only approved files are
indexed. Employee personal documents use ``/employee/*`` and never enter
the shared knowledge base.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import get_document_service
from app.auth import User, require_hr_admin
from app.config import get_settings
from app.exceptions import AppError
from app.ingestion.validator import validate_upload
from app.models.requests import DocumentIngestRequest
from app.models.responses import (
    DocumentInfoResponse,
    DocumentListResponse,
    DocumentSummaryResponse,
    IngestResponse,
)
from app.rag.chain import RagEngine, get_rag_engine
from app.services.document_service import DocumentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Ingest documents from the documents directory (HR/Admin only)",
)
def ingest(
    service: Annotated[DocumentService, Depends(get_document_service)],
    hr: Annotated[User, Depends(require_hr_admin)],
    payload: DocumentIngestRequest | None = None,
) -> IngestResponse:
    """Validated scan: only clearly-HR files are indexed; others are queued."""
    _ = hr
    payload = payload or DocumentIngestRequest()
    if payload.document_name:
        report = service.ingest_validated_scan(
            document_name=payload.document_name, force=payload.force
        )
    else:
        report = service.ingest_validated_scan(force=payload.force)
    if report.failures:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Some documents failed to ingest.",
                "failures": report.failures,
            },
        )
    return IngestResponse(
        status="ok",
        files_found=report.files_found,
        files_processed=report.files_processed,
        files_skipped_unchanged=report.files_skipped_unchanged,
        chunks_added=report.chunks_added,
        chunks_skipped_duplicate=report.chunks_skipped_duplicate,
        failures=report.failures,
    )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents currently indexed (HR/Admin only)",
)
def list_documents(
    service: Annotated[DocumentService, Depends(get_document_service)],
    hr: Annotated[User, Depends(require_hr_admin)],
) -> DocumentListResponse:
    """List the shared knowledge-base documents. HR/Admin only — employees
    must not see the management list (they use the chat assistant and their
    own personal-document summary instead)."""
    _ = hr
    data = service.list_documents()
    return DocumentListResponse(
        documents=[
            DocumentInfoResponse(**entry) for entry in data["documents"]
        ],
        total_documents=data["total_documents"],
        total_chunks=data["total_chunks"],
    )


@router.delete(
    "/{document_name}",
    response_model=dict[str, Any],
    summary="Delete a document and its vectors (HR/Admin only)",
)
def delete_document(
    document_name: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
    hr: Annotated[User, Depends(require_hr_admin)],
) -> dict[str, Any]:
    """Remove a document from the vector index by exact filename."""
    _ = hr
    deleted = service.delete(document_name)
    return {"deleted": document_name, "chunks_removed": deleted}


@router.post(
    "/upload",
    response_model=dict[str, Any],
    summary="Upload a document and ingest it immediately (HR/Admin, validated)",
)
async def upload_document(
    file: Annotated[UploadFile, File()],
    service: Annotated[DocumentService, Depends(get_document_service)],
    hr: Annotated[User, Depends(require_hr_admin)],
) -> dict[str, Any]:
    """Validate, save, and index an uploaded PDF/DOCX/TXT file.

    Even HR uploads are validated: clearly personal/unrelated files are
    rejected/quarantined (422 + Pending Review record) and never indexed.
    """
    settings = get_settings()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the maximum size of {settings.max_upload_size_mb} MB.",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    filename = file.filename or "unnamed"
    # Pre-validation gate: extract text without touching ChromaDB.
    try:
        text = service._extract_text_from_bytes(Path(filename).name, content)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    verdict = validate_upload(Path(filename).name, content, text)
    if verdict.verdict == "rejected":
        record = service.reviews.create(
            filename=Path(filename).name,
            status="rejected",
            reason=verdict.reason,
            category=verdict.category,
            confidence=verdict.confidence,
            uploaded_by=hr.email,
        )
        try:
            service.reviews.save_pending_file(Path(filename).name, content)
        except Exception:
            logger.exception("Failed to quarantine rejected upload '%s'.", filename)
        raise HTTPException(
            status_code=422,
            detail=(
                f"Document rejected: {verdict.reason} "
                f"(review_id={record['review_id']}, status=rejected). "
                "It was NOT added to the shared knowledge base."
            ),
        )
    if verdict.verdict == "pending":
        record = service.reviews.create(
            filename=Path(filename).name,
            status="pending",
            reason=verdict.reason,
            category=verdict.category,
            confidence=verdict.confidence,
            uploaded_by=hr.email,
        )
        try:
            service.reviews.save_pending_file(Path(filename).name, content)
        except Exception:
            logger.exception("Failed to quarantine pending upload '%s'.", filename)
        raise HTTPException(
            status_code=202,
            detail=(
                f"Document held for HR review: {verdict.reason} "
                f"(review_id={record['review_id']}, status=pending). "
                "It was NOT added to the shared knowledge base."
            ),
        )

    try:
        path = service.upload_to_documents_dir(filename, content)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    report = service.ingest(document_name=path.name)
    if report.failures or report.files_processed == 0:
        raise HTTPException(
            status_code=422,
            detail=(
                "The file was saved but could not be indexed. "
                f"Details: {report.failures or 'no text could be extracted'}"
            ),
        )
    service.reviews.create(
        filename=path.name,
        status="approved",
        reason="Validated as company HR/compliance on upload and indexed.",
        category="hr_compliance",
        confidence=verdict.confidence,
        uploaded_by=hr.email,
    )
    return {"filename": path.name, "status": "ok", "chunks_added": report.chunks_added}


# ------------------------------------------------------------------ #
# Approval workflow (HR/Admin only): pending-first uploads
# ------------------------------------------------------------------ #
@router.post(
    "/hr/upload",
    response_model=dict[str, Any],
    status_code=202,
    summary="Stage a company HR document for review (HR/Admin only)",
)
async def hr_upload_for_review(
    file: Annotated[UploadFile, File()],
    service: Annotated[DocumentService, Depends(get_document_service)],
    hr: Annotated[User, Depends(require_hr_admin)],
) -> dict[str, Any]:
    """Upload a company document into Pending Review (never auto-indexed)."""
    settings = get_settings()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the maximum size of {settings.max_upload_size_mb} MB.",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    try:
        record = service.submit_company_document(
            file.filename or "unnamed", content, uploaded_by=hr.email
        )
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return record


@router.get(
    "/review",
    response_model=list[dict[str, Any]],
    summary="List review-queue documents (HR/Admin only)",
)
def list_review_queue(
    service: Annotated[DocumentService, Depends(get_document_service)],
    hr: Annotated[User, Depends(require_hr_admin)],
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List pending/approved/rejected review records, optionally filtered."""
    _ = hr
    if status and status not in {"pending", "approved", "rejected"}:
        raise HTTPException(
            status_code=422, detail="status must be pending, approved or rejected."
        )
    return service.list_reviews(status=status)


@router.post(
    "/review/{review_id}/approve",
    response_model=dict[str, Any],
    summary="Approve a pending document and index it (HR/Admin only)",
)
def approve_review_document(
    review_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
    hr: Annotated[User, Depends(require_hr_admin)],
) -> dict[str, Any]:
    """Approve a pending document; only now is it indexed into ChromaDB."""
    try:
        return service.approve_review(review_id, approver=hr.email)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/review/{review_id}/reject",
    response_model=dict[str, Any],
    summary="Reject/quarantine a document (HR/Admin only)",
)
def reject_review_document(
    review_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
    hr: Annotated[User, Depends(require_hr_admin)],
    reason: str | None = None,
) -> dict[str, Any]:
    """Reject a document; it stays out of ChromaDB (purged if present)."""
    try:
        return service.reject_review(review_id, approver=hr.email, reason=reason)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/{document_name}/summary",
    response_model=DocumentSummaryResponse,
    response_model_exclude_none=True,
    summary="Summarise one indexed document (HR/Admin only)",
)
def summarize_document(
    document_name: str,
    engine: Annotated[RagEngine, Depends(get_rag_engine)],
    hr: Annotated[User, Depends(require_hr_admin)],
) -> DocumentSummaryResponse:
    """Generate a grounded summary for a single indexed document.

    HR/Admin only. Employees summarise their own personal documents via
    ``POST /employee/summarize`` instead.
    """
    _ = hr
    name = Path(document_name).name  # sanitise: strip any path components
    result = engine.summarize_document(name)
    return DocumentSummaryResponse(
        document=name,
        chunk_count=result.chunk_count,
        summary=result.summary,
        model=result.model,
    )
