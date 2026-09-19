"""Application-specific exceptions.

These are mapped to clean HTTP responses in ``app/main.py`` so that API
clients never see stack traces, internal paths, or secrets.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for expected, user-facing application errors."""

    status_code = 500
    message = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message


class ConfigurationError(AppError):
    """Raised when required configuration (e.g. an API key) is missing."""

    status_code = 503
    message = "The application is not fully configured."


class VectorStoreError(AppError):
    """Raised when the vector database cannot be reached or is unhealthy."""

    status_code = 503
    message = "The document vector database is unavailable."


class LLMError(AppError):
    """Raised when the Gemini API call fails."""

    status_code = 502
    message = "The language model service is temporarily unavailable."


class IngestionError(AppError):
    """Raised when document ingestion fails."""

    status_code = 500
    message = "Document ingestion failed."


class DocumentNotFoundError(AppError):
    """Raised when a requested document is not indexed."""

    status_code = 404
    message = "The requested document was not found in the index."


class UnsupportedFileTypeError(AppError):
    """Raised when a file type is not supported for ingestion."""

    status_code = 415
    message = "Unsupported file type. Supported types: .pdf, .docx, .txt"


class ForbiddenError(AppError):
    """Raised when an authenticated user lacks permission for an endpoint."""

    status_code = 403
    message = "Access denied."


class AuthenticationError(AppError):
    """Raised when credentials are missing, invalid or expired (HTTP 401)."""

    status_code = 401
    message = "Not authenticated."


class ConflictError(AppError):
    """Raised when a resource already exists (HTTP 409)."""

    status_code = 409
    message = "The resource already exists."