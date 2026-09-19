"""Tests for the health/root endpoints."""

from __future__ import annotations


def test_root_health_message(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "Enterprise HR Compliance Bot" in body["message"]
    assert body["health"] == "/health"


def test_health_endpoint_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["app_name"] == "Enterprise HR Compliance Bot"
    assert body["status"] in {"ok", "degraded"}
    assert "components" in body
    assert body["components"]["embeddings_provider"] == "dummy"


def test_health_reports_real_providers_and_models(client):
    """The dashboard needs the configured model names visible in /health."""
    response = client.get("/health")
    assert response.status_code == 200
    comps = response.json()["components"]
    assert comps["llm_provider"] == "dummy"
    assert comps["embeddings_provider"] == "dummy"
    assert comps["embedding_model"]  # real configured model, never empty
    assert comps["llm_model"]  # real configured model, never empty


def test_health_missing_route(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404