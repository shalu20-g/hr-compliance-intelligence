"""API-level tests for the document management endpoints."""

from __future__ import annotations

import pytest

from tests.conftest import write_sample_documents


@pytest.fixture
def docs_api():
    """TestClient whose document service uses an isolated Chroma collection.

    Requests run as HR_ADMIN by default (all document-management endpoints
    require it); pass explicit headers to test other roles.
    """
    from fastapi.testclient import TestClient

    from app.api.deps import get_document_service
    from app.main import app
    from app.services.document_service import DocumentService
    from tests.conftest import login_headers, make_engine, make_user, unique_email

    iso_settings = make_engine().settings
    service = DocumentService(iso_settings)

    email = unique_email("hr")
    make_user(email, role="HR_ADMIN")
    app.dependency_overrides[get_document_service] = lambda: service
    with TestClient(app) as client:
        headers = login_headers(client, email)
        yield client, iso_settings, headers
    app.dependency_overrides.clear()


def _read_leave_policy(settings) -> bytes:
    from scripts import make_samples

    return (make_samples.LEAVE_POLICY.strip() + "\n").encode("utf-8")


def test_ingest_via_api(docs_api):
    client, iso_settings, hr = docs_api
    write_sample_documents(iso_settings)

    response = client.post("/documents/ingest", headers=hr)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["files_processed"] >= 3
    assert body["chunks_added"] > 0
    assert body["failures"] == []


def test_ingest_via_api_is_idempotent(docs_api):
    client, iso_settings, hr = docs_api
    write_sample_documents(iso_settings)

    client.post("/documents/ingest", headers=hr)
    second = client.post("/documents/ingest", headers=hr).json()
    assert second["files_processed"] == 0  # nothing changed
    assert second["files_skipped_unchanged"] == second["files_found"]
    assert second["chunks_added"] == 0


def test_list_documents_via_api(docs_api):
    client, iso_settings, hr = docs_api
    write_sample_documents(iso_settings, names=["leave_policy.txt"])
    client.post(
        "/documents/ingest",
        json={"document_name": "leave_policy.txt"},
        headers=hr,
    )
    assert client.post("/documents/ingest", headers=hr).status_code == 200

    response = client.get("/documents", headers=hr)
    assert response.status_code == 200
    body = response.json()
    names = {d["filename"] for d in body["documents"]}
    assert "leave_policy.txt" in names
    assert body["total_documents"] == len(names)
    assert body["total_chunks"] >= 1


def test_delete_document_via_api(docs_api):
    client, iso_settings, hr = docs_api
    write_sample_documents(iso_settings, names=["leave_policy.txt"])
    client.post("/documents/ingest", headers=hr)

    response = client.delete("/documents/leave_policy.txt", headers=hr)
    assert response.status_code == 200
    assert response.json()["deleted"] == "leave_policy.txt"

    body = client.get("/documents", headers=hr).json()
    assert "leave_policy.txt" not in {d["filename"] for d in body["documents"]}


def test_delete_missing_document_via_api_returns_404(docs_api):
    client, _, hr = docs_api
    response = client.delete("/documents/not_indexed.txt", headers=hr)
    assert response.status_code == 404


def test_upload_and_ingest_via_api(docs_api):
    client, iso_settings, hr = docs_api

    files = {"file": ("uploaded_leave.txt", _read_leave_policy(iso_settings), "text/plain")}
    response = client.post("/documents/upload", files=files, headers=hr)
    assert response.status_code == 200
    assert response.json()["chunks_added"] > 0

    body = client.get("/documents", headers=hr).json()
    assert "uploaded_leave.txt" in {d["filename"] for d in body["documents"]}


def test_upload_unsupported_type_rejected(docs_api):
    client, _, hr = docs_api
    files = {"file": ("malware.exe", b"not a policy", "application/octet-stream")}
    response = client.post("/documents/upload", files=files, headers=hr)
    assert response.status_code == 415


def test_upload_empty_file_rejected(docs_api):
    client, _, hr = docs_api
    files = {"file": ("empty.txt", b"", "text/plain")}
    response = client.post("/documents/upload", files=files, headers=hr)
    assert response.status_code in {400, 422}