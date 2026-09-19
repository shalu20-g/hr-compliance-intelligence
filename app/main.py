"""FastAPI application entrypoint for the Enterprise HR Compliance Bot."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes_auth import router as auth_router
from app.api.routes_chat import router as chat_router
from app.api.routes_documents import router as documents_router
from app.api.routes_employee import router as employee_router
from app.api.routes_health import router as health_router
from app.config import get_settings
from app.exceptions import AppError
from app.logging_config import setup_logging

logger = logging.getLogger(__name__)
settings = get_settings()

setup_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "RAG-based chatbot that answers employee questions about HR policies, "
        "compliance rules and the employee handbook using grounded retrieval "
        "and source citations. Sample documents are fictional."
    ),
)

# CORS: allow the Streamlit frontend (and any local client) to talk to the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["root"])
def root() -> dict:
    """Simple health/status message with links to the interactive docs."""
    return {
        "message": "Enterprise HR Compliance Bot (RAG) is running.",
        "docs": "/docs",
        "health": "/health",
        "version": settings.app_version,
    }


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Map domain exceptions to clean HTTP errors (no internals leaked)."""
    logger.error("AppError on %s: %s", request.url.path, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "error_type": type(exc).__name__,
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return a compact 422 body for malformed requests."""
    errors = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", []) if part != "body")
        errors.append({"field": loc, "message": err.get("msg")})
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed.",
            "error_type": "ValidationError",
            "status_code": 422,
            "errors": errors,
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler: never leak stack traces or internals."""
    logger.exception("Unhandled error on %s.", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred. Please try again later.",
            "error_type": "InternalServerError",
            "status_code": 500,
        },
    )


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(employee_router)

logger.info("%s ready (version %s).", settings.app_name, settings.app_version)