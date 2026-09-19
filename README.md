# Enterprise HR Compliance Bot (RAG)

A production-style **Retrieval-Augmented Generation (RAG)** chatbot that lets employees ask natural-language questions about HR policies, compliance rules, the employee handbook, leave policies, workplace policies, benefits and the code of conduct.

The bot **retrieves** the most relevant passages from your uploaded HR/compliance documents and **grounds every answer** on them using Google Gemini, returning **source citations** so users can verify where each answer came from.

> **IMPORTANT:** The sample documents shipped in `data/documents/` are **SAMPLE / FICTIONAL** policies for a fictional company called "Acme Corp". They exist only to demonstrate the pipeline. They are **not** real Acme Corp policies, **not** legal advice, and must not be treated as authoritative for any real organisation.

---

## Overview

Employees type a question, and the bot:

1. embeds the question,
2. searches a persistent **ChromaDB** vector index of the HR documents,
3. keeps only chunks above a configurable **relevance threshold**,
4. hands the retrieved excerpts to **Google Gemini** with a strict anti-hallucination prompt,
5. returns a **cited answer** plus structured source metadata.

If the documents do not contain enough information, the bot *explicitly says so* instead of guessing.

---

## Features

- 📄 **Multi-format ingestion** – PDF (.pdf), Word (.docx) and plain text (.txt)
- 🧠 **RAG pipeline** – ChromaDB similarity search → grounded Gemini generation
- 🛡️ **Hallucination control** – strict prompt rules, relevance thresholding, refusal messages
- 🔎 **Source citations** – `document` + `page` + `section` + `relevance_score` per answer
- ♻️ **De-duplicated ingestion** – content-hash ids; unchanged files are skipped, changed files are re-indexed
- 🚀 **FastAPI REST API** – `/chat`, `/documents/ingest`, `/documents`, `/documents/upload`, `/documents/{name}/summary`, `/health`
- ✅ **Pydantic validation** – validated requests/responses with clean error messages
- 🔐 **Email + password auth (JWT)** – bcrypt hashes, PostgreSQL users table, roles `HR_ADMIN` / `EMPLOYEE` enforced on the backend
- 🗂️ **Approval workflow** – company uploads enter Pending Review; only approved documents reach ChromaDB; personal docs never do
- 🧪 **Tested offline** – pytest suite with a fake Gemini model and mock embeddings
- 🖥️ **Streamlit frontend** (optional) – email/password login, chat UI, document upload/scan/delete, and per-document summaries
- ⚛️ **React frontend** (`frontend-react/`) – Vite + JavaScript, email/password login, role-based HR/Employee dashboards
- 🐳 **Docker** optional

---

## Architecture

```
Frontend (Streamlit or React, email + password → JWT)
       │  Authorization: Bearer <token> on every call
       ▼
Auth layer  (bcrypt verify → JWT → users table in PostgreSQL/SQLite)
       │  HR_ADMIN → ingestion + review + shared-list endpoints (else 403)
       │  EMPLOYEE → chat + personal-document endpoints only
       ▼
data/documents/  (approved HR policies only; pending files quarantined)
       │
       ▼
Document Loader  (PDF / DOCX / TXT → text + metadata)
      │
      ▼
Chunking  (LangChain RecursiveCharacterTextSplitter)
      │
      ▼
Embeddings  (Google Gemini `models/text-embedding-004`)
      │
      ▼
ChromaDB  (persistent vector store: data/chroma_db/)
      │
      ▼
Retriever  (top-k similarity search + relevance threshold)
      │
      ▼
Prompts  (numbered context + strict grounding rules)
      │
      ▼
Google Gemini  (generates the answer model)
      │
      ▼
Source-Cited Response  (answer + document/page/section list)
```

Retrieval is what makes this **RAG**, not a bare LLM:

- The model never answers from "memory" – it only sees the retrieved excerpts.
- Answers can be traced back to the exact document, page and section.
- Low-relevance retrievals are discarded, prompting a truthful "not found" response.

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Language | Python 3.11+ |
| API framework | FastAPI + Uvicorn |
| Orchestration | LangChain (splitters, document objects) |
| Vector store | ChromaDB (persistent) |
| Embeddings | Google Generative AI embeddings |
| Generation | Google Gemini (`langchain-google-genai`) |
| PDF parsing | PyPDF |
| DOCX parsing | python-docx |
| Validation | Pydantic / Pydantic Settings |
| Users database | PostgreSQL (production) / SQLite file (dev) via SQLAlchemy |
| Passwords | bcrypt hashes only — never plain text, never in responses |
| Auth tokens | JWT bearer (PyJWT, HS256) |
| Config | python-dotenv / environment variables |
| Frontend (optional) | Streamlit |
| Frontend | React + Vite (JavaScript) in `frontend-react/` |
| Tests | pytest + httpx |

---

## Project Structure

```
enterprise-hr-compliance-bot/
│
├── app/
│   ├── main.py                  # FastAPI app + global error handlers
│   ├── config.py                # Pydantic Settings (env-driven)
│   ├── exceptions.py            # domain exceptions → clean HTTP errors
│   ├── logging_config.py        # structured logging setup
│   │
│   ├── api/                     # HTTP layer
│   │   ├── deps.py              # FastAPI dependencies (+ DB session)
│   │   ├── routes_auth.py       # POST /auth/register|login|logout, GET /auth/me
│   │   ├── routes_health.py     # GET /health
│   │   ├── routes_chat.py       # POST /chat
│   │   ├── routes_documents.py  # /documents endpoints + HR review workflow
│   │   └── routes_employee.py   # POST /employee/summarize (never indexed)
│   │
│   ├── auth.py                  # bcrypt + JWT + role dependencies
│   ├── database.py              # SQLAlchemy engine/session/init (users DB)
│   │
│   ├── models/
│   │   ├── requests.py          # ChatRequest, DocumentIngestRequest
│   │   ├── responses.py         # ChatResponse, sources, health, etc.
│   │   └── user.py              # users table + register/login schemas
│   │
│   ├── rag/                     # RAG pipeline
│   │   ├── embeddings.py        # Gemini + DummyEmbeddings (offline mode)
│   │   ├── vectorstore.py       # persistent ChromaDB wrapper
│   │   ├── retriever.py         # top-k retrieval + thresholding
│   │   ├── prompt.py            # anti-hallucination prompts
│   │   └── chain.py             # RagEngine: question → cited answer
│   │
│   ├── ingestion/
│   │   ├── loaders.py           # PDF / DOCX / TXT loaders
│   │   ├── chunker.py           # text splitting + metadata + ids
│   │   ├── validator.py         # HR/compliance classification + safety
│   │   └── pipeline.py          # ingest orchestration + dedup
│   │
│   └── services/
│       ├── document_service.py  # list/ingest/delete + review workflow
│       └── review_store.py      # pending/approved/rejected queue
│
├── scripts/
│   ├── ingest.py                # CLI: python scripts/ingest.py
│   ├── init_db.py               # CLI: python scripts/init_db.py (users table)
│   ├── create_admin.py          # CLI: create the first HR_ADMIN account
│   └── make_samples.py          # regenerate the SAMPLE documents
│
├── data/
│   ├── documents/               # your HR PDFs / DOCX / TXT go here
│   └── chroma_db/               # persistent vector index (gitignored)
│
├── tests/                       # pytest suite (offline, mocked Gemini)
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_chat.py
│   ├── test_governance.py       # auth + roles + review workflow
│   ├── test_ingestion.py
│   └── test_retrieval.py
│
├── frontend/
│   └── app.py                   # Streamlit UI (email/password login)
│
├── frontend-react/
│   └── src/                     # React + Vite UI (email/password login)
│
├── .env.example
├── .gitignore
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## Installation

Requires **Python 3.11+**.

```bash
git clone <your-repo-url>
cd enterprise-hr-compliance-bot

python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Then configure your environment (see below).

---

## Environment Variables

Copy the example file and fill in your values:

```bash
cp .env.example .env     # Windows: copy .env.example .env
```

| Variable | Default | Description |
| --- | --- | --- |
| `GOOGLE_API_KEY` | – | **Required for production.** Gemini API key from [AI Studio](https://aistudio.google.com/app/apikey). Never commit it. |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Chat/generation model. |
| `EMBEDDING_MODEL` | `models/text-embedding-004` | Embedding model. |
| `EMBEDDINGS_PROVIDER` | `gemini` | `gemini` or `dummy` (offline dev/test only). |
| `LLM_PROVIDER` | `gemini` | `gemini` or `dummy` – `dummy` is a deterministic offline mock that answers only from retrieved context (offline dev/test only). |
| `CHROMA_PERSIST_DIRECTORY` | `data/chroma_db` | Persistent vector store location. |
| `CHROMA_COLLECTION_NAME` | `hr_compliance_docs` | Chroma collection name. |
| `DOCUMENTS_DIRECTORY` | `data/documents` | Folder scanned by the ingestion pipeline. |
| `TOP_K` | `5` | Number of chunks retrieved per query. |
| `SIMILARITY_THRESHOLD` | `0.55` | Minimum relevance score (0–1) for grounding. |
| `CHUNK_SIZE` | `1000` | Target chunk size (characters). |
| `CHUNK_OVERLAP` | `150` | Chunk overlap (characters). |
| `MAX_QUESTION_LENGTH` | `500` | Reject longer questions. |
| `MAX_UPLOAD_SIZE_MB` | `50` | Upload size limit. |
| `DATABASE_URL` | `sqlite:///./data/app.db` | Users database. Production: `postgresql://user:pass@host:5432/db`. |
| `JWT_SECRET_KEY` | `dev-only-secret-key-change-me` | **Must be a long random secret in production.** |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm. |
| `JWT_EXPIRE_MINUTES` | `480` | Session token lifetime. |

**No secrets are hardcoded.** The API never returns environment values.

**No API key?** The API still starts so you can explore the UI and endpoints. With `EMBEDDINGS_PROVIDER=dummy` **and** `LLM_PROVIDER=dummy`, indexing, retrieval and chat all work offline with deterministic mocks – useful for local testing (not for production search/answer quality). With the providers left on `gemini`, `/chat` returns a clean `503` until a real key is set.

---

## Authentication & Authorization

### Authentication flow

1. `POST /auth/register` with `{name, email, password}` creates an **EMPLOYEE** account (bcrypt hash stored; the hash is never returned). Public registration can never create `HR_ADMIN`.
2. `POST /auth/login` with `{email, password}` returns `{access_token, token_type: "bearer"}` (JWT, subject = user id).
3. The frontend sends `Authorization: Bearer <token>` on every request.
4. The backend re-validates the token and reloads the user (including role) from the users table on each call. Bad/missing/expired tokens → `401`.
5. `POST /auth/logout` ends the client session (tokens are stateless — the client discards its token). `GET /auth/me` returns the profile + server-side role.

### Roles and permissions (enforced on the backend)

| Capability | HR_ADMIN | EMPLOYEE |
| --- | --- | --- |
| Query shared HR knowledge (`POST /chat`) | ✅ | ✅ |
| Upload company HR documents | ✅ | ❌ 403 |
| View pending/approved/rejected reviews | ✅ | ❌ 403 |
| Approve/reject documents | ✅ | ❌ 403 |
| List shared documents / shared summaries | ✅ | ❌ 403 |
| Upload + summarize personal documents | ✅ | ✅ (never indexed into ChromaDB) |

UI sections are hidden by role, but the backend check is authoritative — manually crafted API calls with an EMPLOYEE token are rejected too.

### PostgreSQL setup

```bash
createdb hrbot
# .env:
DATABASE_URL=postgresql://hrbot:CHANGE_ME@localhost:5432/hrbot
```

Apply with `python scripts/init_db.py` (creates the `users` table; safe to re-run). For local development without Postgres, leave the SQLite default.

### Create the first HR_ADMIN

```bash
python scripts/create_admin.py --name "HR Admin" --email hr@company.com
# enter a password when prompted (min 8 chars, bcrypt-hashed)
```

If the email already exists, the account is promoted to `HR_ADMIN`.

### Create / log in as EMPLOYEE

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Alex","email":"alex@company.com","password":"Password123!"}'

curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alex@company.com","password":"Password123!"}'
# → {"access_token":"...","token_type":"bearer"}
```

Log in as HR_ADMIN the same way via `/auth/login` with the admin email/password, then pass `-H "Authorization: Bearer <token>"` on protected calls.

---

## Ingest Documents (HR_ADMIN)

All ingestion endpoints require an HR_ADMIN bearer token:

Drop your `.pdf`, `.docx` and `.txt` HR documents into `data/documents/`, then run:

```bash
python scripts/ingest.py
```

Re-run anytime – unchanged files are skipped, changed files are re-indexed:

```bash
python scripts/ingest.py --force          # re-index everything
python scripts/ingest.py --document leave_policy.txt
```

Or trigger ingestion through the API (HR_ADMIN token required):

```bash
TOKEN=<paste access_token>
curl -X POST http://127.0.0.1:8000/documents/ingest \
  -H "Authorization: Bearer $TOKEN"
```

> The vector database is **persistent** – it is not rebuilt on API startup.

---

## Run API

```bash
uvicorn app.main:app --reload
```

- Interactive API docs (Swagger UI): **http://127.0.0.1:8000/docs**
- ReDoc: **http://127.0.0.1:8000/redoc**

---

## API Documentation

### `GET /`
Status message with links.

### `GET /health`
Application health + component status (ChromaDB, embeddings provider, LLM configured).

### `POST /auth/register` / `POST /auth/login` / `POST /auth/logout` / `GET /auth/me`
Email + password account management and JWT session handling (see Authentication above).

### `POST /chat`
Ask a natural-language question (any authenticated user).

```http
POST /chat
Content-Type: application/json

{ "question": "How many paid leaves can an employee take in a year?" }
```

```json
{
  "answer": "Full-time employees are entitled to 20 days of paid annual leave per year [1], plus 10 paid sick leave days [2]. ...",
  "sources": [
    {
      "document": "leave_policy.txt",
      "page": null,
      "section": "Annual Leave Policy",
      "relevance_score": 0.87
    },
    {
      "document": "employee_handbook.pdf",
      "page": 4,
      "section": "Annual Leave",
      "relevance_score": 0.81
    }
  ],
  "retrieved_context_count": 2,
  "model": "gemini-2.0-flash",
  "latency_ms": 1240,
  "retrieved_chunks": [ "... full retrieved context ..." ]
}
```

### `POST /documents/ingest` (HR_ADMIN)
Trigger ingestion (`{"document_name": "optional"}`, `{"force": true}` optional).

### `GET /documents` (HR_ADMIN)
List indexed documents with chunk counts.

### `POST /documents/upload` (HR_ADMIN)
Upload and immediately index a document (multipart form, field `file`). Validated: personal/unrelated files are rejected or held for review instead.

### `POST /documents/hr/upload` (HR_ADMIN)
Stage a company document into **Pending Review** (never auto-indexed).

### `GET /documents/review?status=` (HR_ADMIN) · `POST /documents/review/{id}/approve|reject` (HR_ADMIN)
Review workflow: only approved documents are indexed into ChromaDB.

### `POST /employee/summarize` (any authenticated user)
Analyse a personal document without indexing it into the shared knowledge base.

### `DELETE /documents/{document_name}`
Remove a document and its vectors.

### `POST /documents/{document_name}/summary`
Generate a grounded summary of one indexed document (LLM summarises only its stored chunks). Returns `document`, `chunk_count`, `summary`, `model`; `404` if the document is not indexed.

---

## Example API Request (curl)

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question": "What is the sick leave policy?"}'
```

```bash
curl -X POST http://127.0.0.1:8000/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@data/documents/leave_policy.txt"
```

---

## Example Questions

- "How many paid leave days can an employee take in a year?"
- "How do I request annual leave?"
- "What is the sick leave policy and do I need a medical certificate?"
- "Can I work remotely and what equipment does the company provide?"
- "What are the standard working hours?"
- "What behaviour does the code of conduct prohibit?"
- "How do I report harassment at work?"
- "How much paid parental leave is available?"
- "What must I do if I suspect a confidentiality breach?"

---

## Streamlit Frontend (optional)

```bash
streamlit run frontend/app.py
```

Email + password login (JWT session) with HR/Employee sections:

- **HR/Admin** – Dashboard, Upload Company HR Document, Pending/Approved/Rejected Documents, Compliance AI, System Status.
- **Employee** – Ask HR Assistant, Upload My Document, summaries of personal documents.

A professional "HR Compliance Intelligence" UI with five sections (sidebar navigation):

- **Dashboard** – live metrics from `/health`: documents/chunks indexed, ChromaDB status, LLM and embedding providers + models.
- **Document Intelligence** – upload a file (`.txt`/`.pdf`/`.docx`) through the real ingestion pipeline (extract → chunk → embed → store in ChromaDB), then generate an automatic structured summary with Gemini.
- **Document Library** – real table of indexed documents (name, type, chunk count, indexed-at, status) with per-document summary and delete actions.
- **Compliance AI** – grounded Q&A with cited sources (document / section / page / relevance) and an "insufficient information" notice when retrieval finds nothing relevant.
- **System Status** – real backend component status (Gemini configured, embeddings, ChromaDB, indexed documents).

All values shown come live from the backend – no fake statistics or answers.

---

## React Frontend (`frontend-react/`)

```bash
cd frontend-react
npm install
npm run dev        # http://localhost:5173
npm run build      # production build into frontend-react/dist/
```

Point at the backend with `VITE_API_URL` (default `http://127.0.0.1:8000`).
Email + password login; the dashboard shown (HR/Admin vs Employee) follows
the role returned by `GET /auth/me`. No RAG logic lives in React.

---

## RAG Explanation

**RAG = Retrieval-Augmented Generation.** Instead of asking the LLM to answer from its own (often wrong) memory, the system first *retrieves* evidence from your documents and only then asks the model to write an answer using that evidence.

1. The question is embedded into a vector.
2. ChromaDB returns the most similar document chunks (top-K).
3. Chunks below the relevance threshold are **discarded**.
4. The surviving chunks are placed in a prompting template with strict rules.
5. Gemini writes the answer, citing excerpts via `[1]`, `[2]`, …
6. The API maps those citations back to real `document / page / section` metadata.

This dramatically reduces hallucinations: if the documents say nothing about a topic, there is no context to ground an answer on, so the bot says so.

---

## Source Citation

Every factual answer is built from retrieved chunks, and every retrieved chunk carries metadata:

- `filename` – source document (e.g. `employee_handbook.pdf`)
- `page` – page number (PDFs)
- `section` – detected section/chunk title
- `relevance_score` – cosine similarity of the chunk to the question

The `sources` array in the response is de-duplicated per `(document, page, section)` and sorted by relevance. Chunks with weak relevance never appear in the response.

---

## Testing

Tests are fully offline – Gemini calls are replaced with a fake model and embeddings with deterministric mock vectors.

```bash
pytest -q
```

Coverage: health endpoint, request validation, document loading (PDF/DOCX/TXT), chunking, ingestion + dedup, retrieval + thresholding, `/chat` behaviour (grounded answers and refusal paths), JWT auth (register/login, wrong password, expired/forged tokens), role enforcement (employee 403s, HR allowed, unauthenticated 401s), the review workflow, and personal-document isolation from ChromaDB. Auth tests run against a disposable SQLite users database.

---

## Limitations

- **The sample documents are fictional** and provided for demonstration only.
- The bot is **not a substitute for professional legal advice** or an official HR consultation. Compliance questions should always be confirmed with qualified professionals.
- Retrieval quality depends on the embedding model and on document structure (tables, scans, and hand-written PDF text extraction can limit recall).
- `EMBEDDINGS_PROVIDER=dummy` mode is for offline development and tests only – it should not be used in production.
- The repository is a portfolio/demonstration project, not a hardened enterprise system.

---

## Docker (optional)

```bash
docker build -t hr-compliance-bot .
docker run --rm -p 8000:8000 --env-file .env hr-compliance-bot
```

The container ingests the sample documents on startup and then serves the API. Docker is optional – local development with `uvicorn` works the same way.