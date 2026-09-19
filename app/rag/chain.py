"""RAG pipeline orchestration.

``RagEngine`` wires the vector store, retriever, prompt and Gemini LLM into a
single grounded question-answering flow:

    question -> embed -> search ChromaDB -> filter by threshold
              -> build prompt -> Gemini -> answer + source citations

The engine is lazy: ChromaDB, embeddings and the LLM are only initialised on
first use, so the API can start even when an API key is missing (requests
then fail gracefully with a clear message).
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Callable

from app.config import Settings, get_settings
from app.exceptions import DocumentNotFoundError, LLMError
from app.rag.embeddings import get_embeddings
from app.rag.prompt import (
    NO_ANSWER_MESSAGE,
    build_messages,
    build_summary_messages,
)
from app.rag.retriever import dedupe_sources, retrieve
from app.rag.vectorstore import VectorStore

logger = logging.getLogger(__name__)

# Callable signature for an injected mock LLM used in offline tests:
#   (system_prompt: str, human_prompt: str) -> str
LLMCallable = Callable[[str, str], str]


def _extract_text(content: object) -> str:
    """Extract plain text from a model response ``content`` payload.

    Handles plain strings as well as the structured content-part lists returned
    by newer langchain-google-genai versions (e.g. ``{'type': 'text',
    'text': '...'}``), so the API always returns a clean string answer.
    """
    if isinstance(content, str):
        return content.strip()

    parts = list(content) if isinstance(content, (list, tuple)) else [content]
    texts: list[str] = []
    for part in parts:
        if isinstance(part, str):
            texts.append(part)
        elif isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str):
                texts.append(text)
        else:
            text = getattr(part, "text", None)
            if isinstance(text, str):
                texts.append(text)
    return "\n".join(texts).strip()


RATE_LIMITED_HINTS = (
    "RESOURCE_EXHAUSTED",
    "quota",
    "rate_limited",
    "rate-limit",
    "too many requests",
    "429",
)
RATE_LIMITED_TYPES = {
    "GoogleRateLimitError",
    "ResourceExhausted",
    "RateLimitError",
    "QuotaExceededError",
}

TIMEOUT_HINTS = ("timeout", "timed out", "deadline exceeded", "deadline_exceeded")
TIMEOUT_TYPES = {"TimeoutError", "ReadTimeout", "ConnectTimeout", "DeadlineExceeded"}

TRANSIENT_HINTS = (
    "temporarily unavailable",
    "service unavailable",
    "server error",
    "internal error",
    "connection reset",
    "connection aborted",
    "connection error",
    "overloaded",
    "503",
    "502",
    "504",
)
TRANSIENT_TYPES = {
    "ServiceUnavailable",
    "InternalServerError",
    "BadGateway",
    "GatewayTimeout",
    "APIConnectionError",
    "ConnectError",
    "RemoteProtocolError",
    "ServerError",
}

MODEL_HINTS = (
    "not found",
    "not supported",
    "unsupported",
    "does not exist",
    "invalid model",
    "model_not_found",
)
MODEL_TYPES = {"NotFound", "InvalidArgument", "ModelNotFoundError"}

AUTH_HINTS = (
    "api key not valid",
    "api_key_invalid",
    "invalid api key",
    "unauthenticated",
    "permission denied",
    "forbidden",
    "401",
    "403",
)
AUTH_TYPES = {
    "Unauthenticated",
    "PermissionDenied",
    "AuthenticationError",
    "PermissionError",
}

# Categories that are worth retrying with a short backoff.
RETRYABLE_CATEGORIES = {"rate_limit", "timeout", "transient"}

_KEY_PATTERNS = (
    (re.compile(r"(key=)[^&\s\"']+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{10,}"), "<redacted>"),
    (re.compile(r"AQ\.[0-9A-Za-z_\-]{10,}"), "<redacted>"),
)


def sanitize_error_text(text: str) -> str:
    """Redact anything that looks like an API key from error text/logs.

    Exceptions raised by the Google SDK can embed request URLs (which may carry
    ``?key=...``); this guarantees secrets never reach a log line or response.
    Never raises: patterns without a capture group use a plain replacement.
    """
    for pattern, replacement in _KEY_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _classify_llm_error(exc: Exception) -> str:
    """Classify a Gemini failure.

    Returns one of ``rate_limit``, ``auth``, ``model``, ``timeout``,
    ``transient`` or ``unknown`` so callers can retry and message correctly.
    """
    name = type(exc).__name__
    lowered = sanitize_error_text(str(exc)).lower()

    if name in RATE_LIMITED_TYPES or any(h.lower() in lowered for h in RATE_LIMITED_HINTS):
        return "rate_limit"
    if name in AUTH_TYPES or any(h in lowered for h in AUTH_HINTS):
        return "auth"
    if name in MODEL_TYPES or any(h in lowered for h in MODEL_HINTS):
        return "model"
    if name in TIMEOUT_TYPES or any(h in lowered for h in TIMEOUT_HINTS):
        return "timeout"
    if name in TRANSIENT_TYPES or any(h in lowered for h in TRANSIENT_HINTS):
        return "transient"
    return "unknown"


def _is_rate_limited(exc: Exception) -> bool:
    """Best-effort detection of Gemini rate-limit / quota failures."""
    return _classify_llm_error(exc) == "rate_limit"


_LLM_ERROR_MESSAGES = {
    "rate_limit": (
        "The AI service is temporarily rate-limited or busy (request quota "
        "reached). Please wait a moment and try again."
    ),
    "timeout": (
        "The AI service took too long to respond. Please try again in a moment."
    ),
    "transient": (
        "The AI service is temporarily unavailable. Please try again in a moment."
    ),
    "model": (
        "The configured AI model is currently unavailable. Please check the "
        "GEMINI_MODEL setting or try again later."
    ),
    "auth": (
        "The AI service rejected the request. The API key may be missing, "
        "invalid or not permitted for this model."
    ),
    "unknown": (
        "The language model service failed to generate an answer. Please try "
        "again later."
    ),
}


class DummyGroundedLLM:
    """Deterministic offline stand-in for Gemini (``LLM_PROVIDER=dummy``).

    The answer is derived from the citation headers of the retrieved context
    only — it never invents policy facts — so the whole RAG stack can be
    verified end-to-end without a real Gemini API key. NOT for production use.
    """

    def __call__(self, system_prompt: str, human_prompt: str) -> str:
        header = ""
        for line in human_prompt.splitlines():
            if line.startswith("["):
                header = line.strip()
                break
        match = re.match(r"^\[(\d+)\] \(source: ([^,\)]+)", header)
        if not match:
            return "No grounded context was available for this question."
        citation, source = match.group(1), match.group(2)
        return (
            f"According to the retrieved document {source}, the requested policy "
            f"information is available and covered by citation [{citation}]. "
            "(Deterministic offline mock answer via LLM_PROVIDER=dummy; set a real "
            "GOOGLE_API_KEY for production answers.)"
        )


@dataclass
class RAGResult:
    """Structured output of a single RAG query."""

    answer: str
    sources: list[dict] = field(default_factory=list)
    contexts: list[dict] = field(default_factory=list)
    retrieved_raw_count: int = 0
    model: str = ""
    latency_ms: int = 0


@dataclass
class SummaryResult:
    """Structured output of a document summary request."""

    summary: str
    chunk_count: int = 0
    model: str = ""


class RagEngine:
    """Composes retrieval + grounded generation into one callable unit."""

    def __init__(
        self,
        settings: Settings | None = None,
        llm: LLMCallable | None = None,
        vectorstore: VectorStore | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        # ``llm`` may be injected by tests (a plain callable returning text).
        self._llm_override = llm
        self._vectorstore = vectorstore
        self._embeddings = None
        self._llm = None

    # ------------------------------------------------------------------ #
    # Lazy component initialisation
    # ------------------------------------------------------------------ #
    @property
    def embeddings(self):
        if self._embeddings is None:
            self._embeddings = get_embeddings(self.settings)
        return self._embeddings

    @property
    def vectorstore(self) -> VectorStore:
        if self._vectorstore is None:
            self._vectorstore = VectorStore(self.settings, self.embeddings)
        return self._vectorstore

    @property
    def llm(self) -> LLMCallable:
        if self._llm is None:
            if self._llm_override is not None:
                self._llm = self._llm_override
            else:
                self._llm = self._build_llm()
        return self._llm

    def _build_llm(self) -> LLMCallable:
        """Build the configured LLM provider (real Gemini or offline dummy)."""
        if self.settings.llm_provider == "dummy":
            logger.warning("Using DummyGroundedLLM mock provider (offline mode only).")
            return DummyGroundedLLM()
        return self._build_gemini_llm()

    def _build_gemini_llm(self) -> LLMCallable:
        """Build a callable that runs the real Gemini chat model."""
        api_key = self.settings.require_api_key()
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:  # pragma: no cover - environment issue
            raise LLMError(
                "langchain-google-genai is not installed. Run `pip install -r requirements.txt`."
            ) from exc

        model = ChatGoogleGenerativeAI(
            model=self.settings.gemini_model,
            google_api_key=api_key,
            temperature=0.0,
            max_output_tokens=1024,
        )
        logger.info("Gemini LLM ready (model=%s).", self.settings.gemini_model)

        def invoke(system_prompt: str, human_prompt: str) -> str:
            try:
                from langchain_core.messages import HumanMessage, SystemMessage

                response = model.invoke(
                    [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]
                )
                return _extract_text(response.content)
            except Exception as exc:
                logger.exception("Gemini API call failed.")
                category = _classify_llm_error(exc)
                raise LLMError(
                    _LLM_ERROR_MESSAGES.get(
                        category, _LLM_ERROR_MESSAGES["unknown"]
                    )
                ) from exc

        return invoke

    # ------------------------------------------------------------------ #
    # Core pipeline
    # ------------------------------------------------------------------ #
    def generate(self, question: str) -> RAGResult:
        """Run the full RAG pipeline for a single question."""
        started = time.perf_counter()

        # 1. Retrieve + filter (also warms up embeddings/vectorstore).
        chunks = retrieve(
            vectorstore=self.vectorstore,
            question=question,
            top_k=self.settings.top_k,
            threshold=self.settings.similarity_threshold,
        )

        # 2. Decide whether we have enough grounding context.
        # Unsupported/unanswerable questions (no chunks above threshold) must
        # return a graceful grounded "not found" answer with HTTP 200 — never
        # raise or return an empty answer (which previously surfaced as 500).
        if not chunks:
            answer = NO_ANSWER_MESSAGE
        else:
            # 3. Grounded generation.
            system, human = build_messages(question, chunks)
            answer = self.llm(system, human)
            if not isinstance(answer, str):
                answer = _extract_text(answer)
            answer = answer.strip() if isinstance(answer, str) else ""
            if not answer:
                # Empty model output is treated as unanswerable, not an error.
                answer = NO_ANSWER_MESSAGE
                chunks = []

        latency_ms = int((time.perf_counter() - started) * 1000)

        sources = [ref.to_dict() for ref in dedupe_sources(chunks)]
        contexts = [c.to_dict() for c in chunks]

        logger.info(
            "RAG query answered in %d ms (contexts=%d, sources=%d).",
            latency_ms,
            len(chunks),
            len(sources),
        )

        return RAGResult(
            answer=answer,
            sources=sources,
            contexts=contexts,
            retrieved_raw_count=len(chunks),
            model=self.settings.gemini_model,
            latency_ms=latency_ms,
        )

    # ------------------------------------------------------------------ #
    # Document summaries
    # ------------------------------------------------------------------ #
    def summarize_document(self, document_name: str) -> SummaryResult:
        """Summarise one indexed document from its stored chunks."""
        name = document_name.strip()
        chunks = self.vectorstore.get_document_chunks(name)
        if not chunks:
            raise DocumentNotFoundError(
                f"Document '{name}' is not present in the index."
            )

        system, human = build_summary_messages(name, chunks)
        summary = self.llm(system, human)

        logger.info("Summarised document '%s' from %d chunk(s).", name, len(chunks))
        return SummaryResult(
            summary=summary,
            chunk_count=len(chunks),
            model=self.settings.gemini_model,
        )

    # ------------------------------------------------------------------ #
    # Diagnostics used by the health endpoint
    # ------------------------------------------------------------------ #
    def status(self) -> dict:
        """Report component availability without raising."""
        status: dict = {
            "chroma_available": False,
            "embeddings_provider": self.settings.embeddings_provider,
            "embedding_model": self.settings.embedding_model,
            "llm_provider": self.settings.llm_provider,
            "llm_model": self.settings.gemini_model,
            "llm_configured": bool(
                self.settings.llm_provider == "dummy"
                or self.settings.has_valid_api_key()
                or self._llm_override is not None
            ),
        }
        try:
            self.vectorstore  # noqa: B018 - force initialisation
            status["chroma_available"] = True
            status["collection"] = self.settings.chroma_collection_name
            status["documents_indexed"] = len(self.vectorstore.list_documents())
            status["chunks_indexed"] = self.vectorstore.count_chunks()
        except Exception as exc:  # noqa: BLE001 - health must never explode
            logger.exception("Health probe failed for ChromaDB.")
            status["error"] = str(exc).splitlines()[0]
        return status


def get_rag_engine() -> RagEngine:
    """FastAPI dependency factory for the shared RAG engine."""
    return RagEngine(get_settings())


__all__ = [
    "RagEngine",
    "RAGResult",
    "SummaryResult",
    "DummyGroundedLLM",
    "get_rag_engine",
    "LLMCallable",
]