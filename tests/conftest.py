"""Shared pytest fixtures and environment bootstrap.

Environment is configured *before* any ``app`` module is imported so that the
cached ``Settings`` and component factories used by the tests point at
isolated temporary directories and the offline ``dummy`` embeddings provider.
No real Gemini API key or network access is required.
"""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

# --- Isolated environment for the whole test session ------------------ #
_TMP_ROOT = Path(tempfile.mkdtemp(prefix="hr_bot_tests_"))
os.environ["CHROMA_PERSIST_DIRECTORY"] = str(_TMP_ROOT / "chroma")
os.environ["DOCUMENTS_DIRECTORY"] = str(_TMP_ROOT / "documents")
os.environ["EMBEDDINGS_PROVIDER"] = "dummy"
os.environ["GOOGLE_API_KEY"] = ""
os.environ["LLM_PROVIDER"] = "dummy"
os.environ["CHUNK_SIZE"] = "200"
os.environ["CHUNK_OVERLAP"] = "20"
os.environ["SIMILARITY_THRESHOLD"] = "0.0"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_ROOT / 'auth_test.db'}"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-not-for-production"

# Ensure the repository root is importable (for `scripts.make_samples`).
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FAKE_ANSWER = "Employees receive 20 days of paid leave per year [1]."


class FakeGeminiLLM:
    """Offline stand-in for the Gemini model used to ground answers."""

    def __init__(self, response: str = FAKE_ANSWER) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def __call__(self, system_prompt: str, human_prompt: str) -> str:
        self.calls.append((system_prompt, human_prompt))
        return self.response


def make_engine(**settings_overrides):
    """Build a RagEngine bound to an isolated Chroma collection and docs dir."""
    from app.config import get_settings
    from app.rag.chain import RagEngine

    base = get_settings()
    token = uuid.uuid4().hex[:10]
    overrides = {
        "chroma_collection_name": f"test_coll_{token}",
        "documents_directory": str(_TMP_ROOT / f"docs_{token}"),
        **settings_overrides,
    }
    settings = base.model_copy(update=overrides)
    return RagEngine(settings, llm=FakeGeminiLLM())


@pytest.fixture
def settings():
    from app.config import get_settings

    return get_settings()


@pytest.fixture
def engine():
    """A RAG engine with an isolated collection and a fake LLM."""
    return make_engine()


@pytest.fixture
def iso_settings():
    """Settings with an isolated Chroma collection per test."""
    return make_engine().settings


@pytest.fixture
def client(engine):
    """FastAPI TestClient with the fake engine injected via dependencies."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.rag.chain import get_rag_engine

    app.dependency_overrides[get_rag_engine] = lambda: engine
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_grounded_engine(settings, names: list[str] | None = None, **overrides):
    """Build an engine whose collection already contains ingested documents."""
    from app.ingestion.pipeline import ingest_documents

    engine = make_engine(**overrides)
    write_sample_documents(engine.settings, names=names)
    ingest_documents(settings=engine.settings)
    return engine


@pytest.fixture
def grounded_client(settings):
    """TestClient with a fake engine that has real ingested documents."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.rag.chain import get_rag_engine

    engine = make_grounded_engine(settings, names=["leave_policy.txt"])
    app.dependency_overrides[get_rag_engine] = lambda: engine
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def write_sample_documents(settings, names: list[str] | None = None) -> Path:
    """Write a realistic set of sample documents into the docs directory."""
    from scripts import make_samples

    docs_dir = Path(settings.documents_directory)
    docs_dir.mkdir(parents=True, exist_ok=True)

    text_docs = {
        "leave_policy.txt": make_samples.LEAVE_POLICY,
        "remote_work_policy.txt": make_samples.REMOTE_WORK_POLICY,
        "parental_leave_policy.txt": make_samples.PARENTAL_LEAVE_POLICY,
        "code_of_conduct.txt": make_samples.CODE_OF_CONDUCT,
        "workplace_harassment_policy.txt": make_samples.HARASSMENT_POLICY,
        "confidentiality_policy.txt": make_samples.CONFIDENTIALITY_POLICY,
    }

    if names is None:
        for name, content in text_docs.items():
            (docs_dir / name).write_text(content.strip() + "\n", encoding="utf-8")
        (docs_dir / "employee_handbook.pdf").write_bytes(
            make_samples.build_pdf_output()
        )
        (docs_dir / "employee_handbook.docx").write_bytes(
            make_samples.build_docx_output()
        )
    else:
        for name in names:
            if name in text_docs:
                (docs_dir / name).write_text(
                    text_docs[name].strip() + "\n", encoding="utf-8"
                )
            elif name == "employee_handbook.pdf":
                (docs_dir / name).write_bytes(make_samples.build_pdf_output())
            elif name == "employee_handbook.docx":
                (docs_dir / name).write_bytes(make_samples.build_docx_output())
    return docs_dir


__all__ = [
    "FAKE_ANSWER",
    "FakeGeminiLLM",
    "make_engine",
    "write_sample_documents",
    "make_user",
    "login_headers",
]


# ------------------------------------------------------------------ #
# Authentication helpers (real JWT flow against the test SQLite DB)
# ------------------------------------------------------------------ #
def make_user(email: str, password: str = "Password123!", name: str = "Test User", role: str = "EMPLOYEE"):
    """Create a user directly in the test database and return its profile."""
    from app.auth import hash_password
    from app.database import get_session_factory, init_db
    from app.models.user import UserRecord

    init_db()
    session = get_session_factory()()
    try:
        record = UserRecord(
            name=name,
            email=email.strip().lower(),
            password_hash=hash_password(password),
            role=role,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return {"id": record.id, "email": record.email, "role": record.role}
    finally:
        session.close()


def login_headers(client, email: str, password: str = "Password123!") -> dict:
    """Log in through the real endpoint and return an Authorization header."""
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def hr_headers(client):
    """Authorization header for a freshly created HR_ADMIN user."""
    email = unique_email("hr")
    make_user(email, role="HR_ADMIN", name="HR Admin")
    return login_headers(client, email)


@pytest.fixture
def emp_headers(client):
    """Authorization header for a freshly created EMPLOYEE user."""
    email = unique_email("emp")
    make_user(email, role="EMPLOYEE", name="Employee")
    return login_headers(client, email)