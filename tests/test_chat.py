"""Tests for the /chat endpoint: validation, grounded answers, low-context refusal."""

from __future__ import annotations

import pytest

from app.exceptions import LLMError
from app.rag.chain import RagEngine, _extract_text
from app.rag.prompt import NO_ANSWER_MESSAGE
from tests.conftest import FAKE_ANSWER, make_engine, make_grounded_engine, write_sample_documents


def test_chat_with_empty_question_rejected(client):
    response = client.post("/chat", json={"question": "   "})
    assert response.status_code == 422


def test_chat_with_missing_question_rejected(client):
    response = client.post("/chat", json={})
    assert response.status_code == 422


def test_chat_with_non_string_question_rejected(client):
    response = client.post("/chat", json={"question": 1234})
    assert response.status_code == 422


def test_chat_with_very_long_question_rejected(client):
    question = "a" * 600  # exceeds MAX_QUESTION_LENGTH (500)
    response = client.post("/chat", json={"question": question})
    assert response.status_code == 422


def test_chat_with_malformed_json_rejected(client):
    response = client.post(
        "/chat",
        data="{not valid json",
        headers={"content-type": "application/json"},
    )
    assert response.status_code in {400, 422}


def test_chat_returns_grounded_answer_with_sources(grounded_client):
    """With a single leave policy ingested, /chat returns an answer + sources."""
    response = grounded_client.post(
        "/chat", json={"question": "How much annual leave do employees get?"}
    )
    assert response.status_code == 200

    body = response.json()
    assert body["answer"]
    assert isinstance(body["sources"], list)
    assert len(body["sources"]) >= 1
    for source in body["sources"]:
        assert source["document"]
        assert "section" in source
        assert 0.0 <= source["relevance_score"] <= 1.0
    assert body["retrieved_context_count"] >= 1
    assert body["model"]
    assert isinstance(body["latency_ms"], int) and body["latency_ms"] >= 0


def test_llm_receives_grounded_prompt_with_citations(settings):
    """The injected LLM must observe a prompt containing the citation header."""
    engine = make_grounded_engine(settings, names=["leave_policy.txt"])

    result = engine.generate("How much annual leave do employees get?")
    assert result.answer == FAKE_ANSWER

    system_prompt, human_prompt = engine._llm_override.calls[0]
    assert "[1] (source:" in human_prompt  # numbered, attributed context
    assert "leave_policy.txt" in human_prompt


def test_chat_refuses_when_no_documents_available(client):
    """Without indexed documents the bot must refuse rather than invent."""
    response = client.post(
        "/chat",
        json={"question": "What is the maximum bonus payout in 2026?"},
    )
    body = response.json()
    assert NO_ANSWER_MESSAGE in body["answer"]
    assert body["sources"] == []
    assert body["retrieved_context_count"] == 0


def test_generate_refuses_when_context_below_threshold(settings):
    """Setting a very strict relevance threshold forces a no-answer response."""
    engine = make_grounded_engine(
        settings, names=["leave_policy.txt"], similarity_threshold=0.999
    )

    result = engine.generate("How much annual leave do employees get?")
    assert result.answer == NO_ANSWER_MESSAGE
    assert result.sources == []
    assert result.retrieved_raw_count == 0


def test_dummy_llm_provider_answers_in_offline_mode():
    """With LLM_PROVIDER=dummy the full stack runs without a Gemini API key."""
    from app.ingestion.pipeline import ingest_documents

    base = make_engine()
    engine = RagEngine(base.settings)  # drop the fake-LLM override
    write_sample_documents(base.settings, names=["leave_policy.txt"])
    ingest_documents(settings=base.settings)

    result = engine.generate("How much annual leave do employees get?")
    assert result.answer
    assert "leave_policy.txt" in result.answer
    assert len(result.sources) >= 1


def test_extract_text_handles_structured_content_parts():
    """LLM content can be a string or a list of content-part dicts."""
    assert _extract_text("plain answer") == "plain answer"
    assert _extract_text("  padded  ") == "padded"

    parts = [
        {"type": "text", "text": "First sentence."},
        {"type": "text", "text": "Second sentence."},
    ]
    assert _extract_text(parts) == "First sentence.\nSecond sentence."

    # empty / exotic payloads must never produce the Python repr
    assert _extract_text([]) == ""
    assert _extract_text(None) == ""


def test_gemini_mode_without_api_key_fails_gracefully():
    """Production mode without an API key returns a clean 503, not a 500."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.rag.chain import RagEngine, get_rag_engine

    base = make_engine(
        embeddings_provider="gemini",
        llm_provider="gemini",
        google_api_key="",
    )
    engine = RagEngine(base.settings)  # no LLM override
    app.dependency_overrides[get_rag_engine] = lambda: engine
    with TestClient(app) as test_client:
        response = test_client.post(
            "/chat", json={"question": "What is the bonus policy?"}
        )
    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "GOOGLE_API_KEY" in response.json()["detail"]
    assert response.json()["error_type"] == "ConfigurationError"


# ------------------------------------------------------------------ #
# Document summaries
# ------------------------------------------------------------------ #
def test_summarize_document_uses_ingested_chunks(settings):
    """Summaries are grounded in the document's stored chunks, in order."""
    engine = make_grounded_engine(settings, names=["leave_policy.txt"])

    result = engine.summarize_document("leave_policy.txt")
    assert result.summary == FAKE_ANSWER
    assert result.chunk_count >= 1
    assert result.model

    system_prompt, human_prompt = engine._llm_override.calls[0]
    assert "summary" in system_prompt.lower()
    assert "leave_policy.txt" in human_prompt
    assert "(section:" in human_prompt  # ordered context headers


def test_summarize_unknown_document_raises(settings):
    """Summarising a document that is not indexed raises DocumentNotFoundError."""
    engine = make_grounded_engine(settings, names=["leave_policy.txt"])

    from app.exceptions import DocumentNotFoundError

    with pytest.raises(DocumentNotFoundError):
        engine.summarize_document("does_not_exist.txt")

    assert engine._llm_override.calls == []  # missing doc must not call the LLM


def test_document_summary_via_api_returns_summary(grounded_client):
    """POST /documents/{name}/summary returns the generated summary."""
    from tests.conftest import login_headers, make_user, unique_email

    email = unique_email("hr")
    make_user(email, role="HR_ADMIN")
    hr = login_headers(grounded_client, email)
    response = grounded_client.post(
        "/documents/leave_policy.txt/summary", headers=hr
    )
    assert response.status_code == 200

    body = response.json()
    assert body["document"] == "leave_policy.txt"
    assert body["summary"] == FAKE_ANSWER
    assert body["chunk_count"] >= 1
    assert body["model"]


def test_document_summary_via_api_unknown_document_404(grounded_client):
    """Summarising an unknown document returns a clean 404."""
    from tests.conftest import login_headers, make_user, unique_email

    email = unique_email("hr")
    make_user(email, role="HR_ADMIN")
    hr = login_headers(grounded_client, email)
    response = grounded_client.post(
        "/documents/not_indexed.txt/summary", headers=hr
    )
    assert response.status_code == 404
    assert response.json()["error_type"] == "DocumentNotFoundError"


# ------------------------------------------------------------------ #
# LLM failure messaging
# ------------------------------------------------------------------ #
def _fake_gemini_chat_with(exc: Exception):
    """Patch ChatGoogleGenerativeAI so .invoke() raises the given error."""

    class FakeChat(object):
        def __init__(self, **kwargs):
            pass

        def invoke(self, messages):
            raise exc

    return FakeChat


def test_llm_rate_limit_returns_clear_message(settings, monkeypatch):
    """Quota/rate-limit failures must produce an actionable 502 message."""
    from app.rag.chain import RagEngine

    engine = RagEngine(
        make_engine(llm_provider="gemini", google_api_key="fake-key").settings
    )
    rate_limited = type("GoogleRateLimitError", (RuntimeError,), {})(
        "Error calling model 'gemini-3.6-flash' (RESOURCE_EXHAUSTED): "
        "429 You exceeded your current quota."
    )
    monkeypatch.setattr(
        "langchain_google_genai.ChatGoogleGenerativeAI",
        _fake_gemini_chat_with(rate_limited),
    )

    invoke = engine._build_gemini_llm()
    with pytest.raises(LLMError) as exc_info:
        invoke("system prompt", "human prompt")
    assert exc_info.value.status_code == 502
    assert "rate-limited" in exc_info.value.message


def test_llm_generic_failure_keeps_generic_message(settings, monkeypatch):
    """Non-quota failures keep the original generic 502 message."""
    from app.rag.chain import RagEngine

    engine = RagEngine(
        make_engine(llm_provider="gemini", google_api_key="fake-key").settings
    )
    monkeypatch.setattr(
        "langchain_google_genai.ChatGoogleGenerativeAI",
        _fake_gemini_chat_with(RuntimeError("backend exploded")),
    )

    invoke = engine._build_gemini_llm()
    with pytest.raises(LLMError) as exc_info:
        invoke("system prompt", "human prompt")
    assert exc_info.value.status_code == 502
    assert "failed to generate" in exc_info.value.message
    assert "rate-limited" not in exc_info.value.message


# ------------------------------------------------------------------ #
# Regression: "Can I take a rest day?" must never 500
# ------------------------------------------------------------------ #
def test_chat_rest_day_returns_graceful_not_found(client):
    """Unsupported 'rest day' question returns 200 + grounded refusal, not 500."""
    response = client.post("/chat", json={"question": "Can I take a rest day?"})
    assert response.status_code == 200
    body = response.json()
    assert NO_ANSWER_MESSAGE in body["answer"]
    assert body["sources"] == []
    assert body["retrieved_context_count"] == 0


def test_chat_rest_day_with_strict_threshold_returns_not_found(settings):
    """Even with docs indexed, an unanswerable query refuses gracefully."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.rag.chain import get_rag_engine

    engine = make_grounded_engine(
        settings, names=["leave_policy.txt"], similarity_threshold=0.999
    )
    app.dependency_overrides[get_rag_engine] = lambda: engine
    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/chat", json={"question": "Can I take a rest day?"}
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert NO_ANSWER_MESSAGE in body["answer"]
    assert body["sources"] == []
    assert body["retrieved_context_count"] == 0


def test_sanitize_error_text_never_raises():
    """Error sanitiser must handle plain text and key-like secrets safely."""
    from app.rag.chain import sanitize_error_text

    assert sanitize_error_text("plain backend exploded") == "plain backend exploded"
    redacted = sanitize_error_text("failed with key=SECRET123 and more")
    assert "SECRET123" not in redacted
    assert sanitize_error_text("key AIzaSyD1234567890abcdefg end") != ""


def test_empty_llm_output_maps_to_not_found(settings):
    """An empty model reply is treated as unanswerable, not an empty 200."""
    from tests.conftest import FakeGeminiLLM

    engine = make_grounded_engine(settings, names=["leave_policy.txt"])
    engine._llm_override = FakeGeminiLLM(response="   ")
    # Bypass cached llm property so the empty-output override is used.
    engine._llm = engine._llm_override
    result = engine.generate("How much annual leave do employees get?")
    assert result.answer == NO_ANSWER_MESSAGE
    assert result.sources == []
    assert result.retrieved_raw_count == 0