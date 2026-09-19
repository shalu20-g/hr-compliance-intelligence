"""Employee personal-document endpoints (never touch shared ChromaDB)."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import get_document_service
from app.auth import User, get_current_user
from app.config import get_settings
from app.exceptions import AppError
from app.services.document_service import DocumentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/employee", tags=["employee"])


@router.post("/summarize", summary="Analyse a personal document (not indexed)")
async def summarize_personal_document(
    file: Annotated[UploadFile, File()],
    service: Annotated[DocumentService, Depends(get_document_service)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Accept an employee's personal file and return a summary.

    The file is analysed from raw bytes only. It is NEVER written to the
    shared documents directory and NEVER indexed into ChromaDB, so it cannot
    affect RAG answers for anyone else.
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
    try:
        result = service.analyze_employee_document(
            file.filename or "unnamed", content, owner=user.email
        )
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return result
