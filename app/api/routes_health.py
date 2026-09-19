"""Health and status endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.models.responses import HealthResponse
from app.rag.chain import RagEngine, get_rag_engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Application health and component status",
)
def health(
    engine: Annotated[RagEngine, Depends(get_rag_engine)],
) -> HealthResponse:
    """Report overall health plus the status of ChromaDB and the LLM."""
    settings = get_settings()
    components = engine.status()
    overall = "ok" if components.get("chroma_available") else "degraded"
    logger.info("Health check: status=%s components=%s", overall, components)
    return HealthResponse(
        status=overall,
        app_name=settings.app_name,
        version=settings.app_version,
        components=components,
    )