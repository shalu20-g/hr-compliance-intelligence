"""Regression tests for HR authorization + document validation workflow.

Authentication uses the real JWT flow: helpers below create users in the
test database and log in through ``POST /auth/login``.
"""

from __future__ import annotations

import pytest

LEAVE_DOC = (
    "Annual Leave Policy\n\nFull-time employees are entitled to 20 working days "
    "of paid annual leave per calendar year. Requests must be submitted through "
    "the HR portal at least 7 working days in advance. Compliance with this "
    "workplace policy is required under the employee handbook and code of conduct."
)

RESUME_DOC = (
    "John Doe Resume\n\nExperienced line cook seeking new opportunities. "
    "Work history: diner 2019-2024. Skills: grilling, prep, teamwork. "
    "Contact: johndoe personal email, passport No X1234567. "
    "Dear hiring manager, this is my job application and cover letter."
)


@pytest.fixture
def gov_api():
    """Isolated TestClient with fresh service, RAG engine and review store."""
    from fastapi.testclient import TestClient

    from app.api.deps import get_document_service
    from app.main import app
    from app.rag.chain import get_rag_engine
    from app.services.document_service import DocumentService
    from tests.conftest import make_engine

    engine = make_engine()
    service = DocumentService(engine.settings)
    app.dependency_overrides[get_document_service] = lambda: service
    app.dependency_overrides[get_rag_engine] = lambda: engine
    with TestClient(app) as client:
        yield client, service, engine
    app.dependency_overrides.clear()


def _hr(client) -> dict:
    """Fresh HR_ADMIN login headers (real JWT via the login endpoint)."""
    from tests.conftest import login_headers, make_user, unique_email

    email = unique_email("hr")
    make_user(email, role="HR_ADMIN", name="HR Admin")
    return login_headers(client, email)


def _emp(client) -> dict:
    """Fresh EMPLOYEE login headers (real JWT via the login endpoint)."""
    from tests.conftest import login_headers, make_user, unique_email

    email = unique_email("emp")
    make_user(email, role="EMPLOYEE", name="Employee")
    return login_headers(client, email)


def _indexed_names(client, headers) -> set[str]:
    body = client.get("/documents", headers=headers).json()
    return {d["filename"] for d in body.get("documents", [])}


# 1. Authorization -------------------------------------------------- #
def test_employee_cannot_access_hr_ingestion_endpoints(gov_api):
    client, _, _ = gov_api
    assert client.post("/documents/ingest", headers=_emp(client)).status_code == 403

    files = {"file": ("policy.txt", LEAVE_DOC.encode(), "text/plain")}
    assert client.post("/documents/upload", files=files, headers=_emp(client)).status_code == 403
    assert client.post("/documents/hr/upload", files=files, headers=_emp(client)).status_code == 403
    assert client.delete("/documents/leave_policy.txt", headers=_emp(client)).status_code == 403
    assert client.get("/documents/review", headers=_emp(client)).status_code == 403
    # Shared management views are HR-only too: no Approved Documents list
    # and no shared-document summaries for employees.
    assert client.get("/documents", headers=_emp(client)).status_code == 403
    assert (
        client.post("/documents/leave_policy.txt/summary", headers=_emp(client)).status_code
        == 403
    )


def test_hr_keeps_access_to_shared_doc_views(gov_api):
    """HR/Admin can still list the shared knowledge base and summarise it."""
    from tests.conftest import write_sample_documents
    from app.ingestion.pipeline import ingest_documents

    client, service, _ = gov_api
    write_sample_documents(service.settings, names=["leave_policy.txt"])
    ingest_documents(settings=service.settings)

    listing = client.get("/documents", headers=_hr(client))
    assert listing.status_code == 200
    assert "leave_policy.txt" in {
        d["filename"] for d in listing.json()["documents"]
    }

    summary = client.post(
        "/documents/leave_policy.txt/summary", headers=_hr(client)
    )
    assert summary.status_code == 200
    assert summary.json()["summary"]


def test_employee_keeps_chat_and_personal_summary_access(gov_api):
    """Lockdown must not break the employee's own allowed surfaces."""
    client, _, _ = gov_api
    chat = client.post("/chat", json={"question": "Can I take a rest day?"}, headers=_emp(client))
    assert chat.status_code == 200

    files = {"file": ("mine.txt", b"My personal notes. I prefer morning shifts.", "text/plain")}
    personal = client.post("/employee/summarize", files=files, headers=_emp(client))
    assert personal.status_code == 200
    assert personal.json()["indexed"] is False


def test_forged_or_tampered_token_rejected(gov_api):
    """Crafted tokens are rejected; roles come only from the database."""
    client, _, _ = gov_api
    hr = _hr(client)
    token = hr["Authorization"].split(" ", 1)[1]
    tampered = token[:-2] + ("ab" if not token.endswith("ab") else "cd")
    bad = {"Authorization": f"Bearer {tampered}"}
    assert client.post("/documents/ingest", headers=bad).status_code == 401
    assert client.get("/auth/me", headers=bad).status_code == 401


def test_auth_me_returns_server_side_role(gov_api):
    client, _, _ = gov_api
    assert client.get("/auth/me", headers=_hr(client)).json()["role"] == "HR_ADMIN"
    me = client.get("/auth/me", headers=_emp(client)).json()
    assert me["role"] == "EMPLOYEE"
    assert "password_hash" not in me
    assert "password" not in me


# Authentication ------------------------------------------------------ #
def test_employee_registration_and_login_succeed(gov_api):
    from tests.conftest import unique_email

    client, _, _ = gov_api
    email = unique_email("newemp")
    created = client.post(
        "/auth/register",
        json={"name": "New Employee", "email": email, "password": "Password123!"},
    )
    assert created.status_code == 201
    assert created.json()["role"] == "EMPLOYEE"
    assert "password_hash" not in created.json()

    logged_in = client.post(
        "/auth/login", json={"email": email, "password": "Password123!"}
    )
    assert logged_in.status_code == 200
    assert logged_in.json()["token_type"] == "bearer"
    assert logged_in.json()["access_token"]

    me = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {logged_in.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["role"] == "EMPLOYEE"


def test_hr_admin_login_succeeds(gov_api):
    from tests.conftest import login_headers, make_user, unique_email

    client, _, _ = gov_api
    email = unique_email("hr")
    make_user(email, role="HR_ADMIN", name="HR Admin")
    headers = login_headers(client, email)
    me = client.get("/auth/me", headers=headers).json()
    assert me["role"] == "HR_ADMIN"
    assert me["email"] == email


def test_login_with_invalid_password_rejected(gov_api):
    from tests.conftest import make_user, unique_email

    client, _, _ = gov_api
    email = unique_email("emp")
    make_user(email, password="Password123!")
    resp = client.post(
        "/auth/login", json={"email": email, "password": "WrongPassword1!"}
    )
    assert resp.status_code == 401


def test_login_with_unknown_email_rejected(gov_api):
    from tests.conftest import unique_email

    client, _, _ = gov_api
    resp = client.post(
        "/auth/login",
        json={"email": unique_email("ghost"), "password": "Password123!"},
    )
    assert resp.status_code == 401


def test_public_registration_cannot_create_hr_admin(gov_api):
    from tests.conftest import unique_email

    client, _, _ = gov_api
    email = unique_email("wannabe")
    created = client.post(
        "/auth/register",
        json={"name": "Wannabe Admin", "email": email, "password": "Password123!"},
    )
    assert created.status_code == 201
    assert created.json()["role"] == "EMPLOYEE"


def test_duplicate_registration_rejected(gov_api):
    from tests.conftest import make_user, unique_email

    client, _, _ = gov_api
    email = unique_email("dupe")
    make_user(email)
    resp = client.post(
        "/auth/register",
        json={"name": "Dupe", "email": email, "password": "Password123!"},
    )
    assert resp.status_code == 409


def test_unauthenticated_protected_endpoints_rejected(gov_api):
    client, _, _ = gov_api
    assert client.post("/documents/ingest").status_code == 401
    assert client.get("/documents").status_code == 401
    assert client.get("/documents/review").status_code == 401
    assert client.post("/documents/x.txt/summary").status_code == 401
    files = {
        "file": (
            "p.txt",
            b"Annual Leave Policy. HR compliance workplace policy.",
            "text/plain",
        )
    }
    assert client.post("/documents/hr/upload", files=files).status_code == 401
    assert client.post("/employee/summarize", files=files).status_code == 401
    assert client.get("/auth/me").status_code == 401


def test_employee_cannot_approve_or_reject_reviews(gov_api):
    client, _, _ = gov_api
    hr = _hr(client)
    emp = _emp(client)
    files = {"file": ("leave_policy.txt", LEAVE_DOC.encode(), "text/plain")}
    staged = client.post("/documents/hr/upload", files=files, headers=hr).json()
    rid = staged["review_id"]
    assert client.post(f"/documents/review/{rid}/approve", headers=emp).status_code == 403
    assert client.post(f"/documents/review/{rid}/reject", headers=emp).status_code == 403


# 2/3. Validation --------------------------------------------------- #
def test_hr_can_submit_company_document_to_pending(gov_api):
    client, _, _ = gov_api
    files = {"file": ("leave_policy.txt", LEAVE_DOC.encode(), "text/plain")}
    resp = client.post("/documents/hr/upload", files=files, headers=_hr(client))
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] in {"pending", "approved"}
    assert body["reason"]
    assert body["review_id"]


def test_unrelated_document_rejected_or_pending_not_indexed(gov_api):
    client, service, _ = gov_api
    before = service.list_documents()["total_chunks"]
    files = {"file": ("resume.txt", RESUME_DOC.encode(), "text/plain")}
    resp = client.post("/documents/hr/upload", files=files, headers=_hr(client))
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] in {"pending", "rejected"}
    assert body["reason"]
    # Must not be indexed.
    assert "resume.txt" not in _indexed_names(client, _hr(client))
    assert service.list_documents()["total_chunks"] == before


def test_legacy_upload_rejects_personal_document(gov_api):
    client, _, _ = gov_api
    files = {"file": ("resume.txt", RESUME_DOC.encode(), "text/plain")}
    resp = client.post("/documents/upload", files=files, headers=_hr(client))
    assert resp.status_code in {202, 422}
    assert "resume.txt" not in _indexed_names(client, _hr(client))


# 4/5. Approval workflow -------------------------------------------- #
def test_pending_document_not_present_until_approved(gov_api):
    client, service, _ = gov_api
    files = {"file": ("leave_policy.txt", LEAVE_DOC.encode(), "text/plain")}
    staged = client.post("/documents/hr/upload", files=files, headers=_hr(client)).json()
    review_id = staged["review_id"]
    # Pending (or freshly staged) must not affect ChromaDB.
    pending = client.get("/documents/review", params={"status": "pending"}, headers=_hr(client)).json()
    if staged["status"] == "pending":
        assert review_id in {r["review_id"] for r in pending}
        assert "leave_policy.txt" not in _indexed_names(client, _hr(client))

    approved = client.post(
        f"/documents/review/{review_id}/approve", headers=_hr(client)
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert "leave_policy.txt" in _indexed_names(client, _hr(client))
    assert service.list_documents()["total_chunks"] > 0


def test_rejected_document_never_indexed(gov_api):
    client, _, _ = gov_api
    files = {"file": ("resume.txt", RESUME_DOC.encode(), "text/plain")}
    staged = client.post("/documents/hr/upload", files=files, headers=_hr(client)).json()
    rid = staged["review_id"]
    resp = client.post(f"/documents/review/{rid}/reject", headers=_hr(client))
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert "resume.txt" not in _indexed_names(client, _hr(client))


def test_validated_scan_indexes_only_hr_docs(gov_api):
    client, service, _ = gov_api
    docs_dir = service.settings.documents_directory
    from pathlib import Path

    Path(docs_dir).mkdir(parents=True, exist_ok=True)
    (Path(docs_dir) / "leave_policy.txt").write_text(LEAVE_DOC, encoding="utf-8")
    (Path(docs_dir) / "resume.txt").write_text(RESUME_DOC, encoding="utf-8")

    resp = client.post("/documents/ingest", headers=_hr(client))
    assert resp.status_code == 200
    names = _indexed_names(client, _hr(client))
    assert "leave_policy.txt" in names
    assert "resume.txt" not in names


# 6. Employee personal documents ------------------------------------ #
def test_employee_personal_document_never_enters_chroma(gov_api):
    client, service, _ = gov_api
    before_docs = _indexed_names(client, _hr(client))
    before_chunks = service.list_documents()["total_chunks"]

    files = {"file": ("my_resume.txt", RESUME_DOC.encode(), "text/plain")}
    resp = client.post("/employee/summarize", files=files, headers=_emp(client))
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]
    assert body["indexed"] is False
    assert "NOT added" in body["note"] or "never" in body["note"].lower()

    assert _indexed_names(client, _hr(client)) == before_docs
    assert service.list_documents()["total_chunks"] == before_chunks
