"""Chat endpoint: the core RAG question-answering API."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from app.models.requests import ChatRequest
from app.models.responses import (
    ChatResponse,
    RetrievedChunkResponse,
    SourceReferenceResponse,
)
from app.rag.chain import RagEngine, get_rag_engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    response_model_exclude_none=True,
    summary="Ask a question about HR/compliance documents",
)
def chat(
    payload: ChatRequest,
    engine: Annotated[RagEngine, Depends(get_rag_engine)],
) -> ChatResponse:
    """Run the RAG pipeline over the question and return a cited answer."""
    result = engine.generate(payload.question)
    return ChatResponse(
        answer=result.answer,
        sources=[SourceReferenceResponse(**s) for s in result.sources],
        retrieved_context_count=result.retrieved_raw_count,
        model=result.model,
        latency_ms=result.latency_ms,
        retrieved_chunks=[
            RetrievedChunkResponse(**c) for c in result.contexts
        ],
    )