# HR Compliance Intelligence — React Frontend

Vite + React (JavaScript) frontend for the existing FastAPI backend.
Both this app and the Streamlit app in `frontend/` use the same
email + password (JWT) login.

## Backend contract

The backend stays exactly as-is (FastAPI + LangChain RAG + ChromaDB + Gemini).
This app only calls its REST endpoints (see `src/api/client.js`):

- `POST /auth/login` `{email, password}` → `{access_token, token_type}` (bearer).
- `GET /auth/me` (bearer) → `{id, name, email, role}` with role `HR_ADMIN` | `EMPLOYEE`.
- `POST /chat` `{question}` → `{answer, sources[], retrieved_context_count, model, latency_ms, retrieved_chunks[]}`
- `GET /documents` (HR) → `{documents[], total_documents, total_chunks}`
- `POST /documents/hr/upload` (multipart, HR) → `202` review record
- `GET /documents/review?status=` (HR) → review list
- `POST /documents/review/{id}/approve|reject` (HR)
- `DELETE /documents/{name}` (HR)
- `POST /documents/{name}/summary` (HR) → `{document, chunk_count, summary, model}`
- `POST /employee/summarize` (multipart) → `{filename, summary, char_count, indexed, note}`
- `GET /health` → `{status, app_name, version, components}`

No RAG logic lives in React.

## Run

```bash
cd frontend-react
npm install
npm run dev        # http://localhost:5173
```

Point at the backend with `VITE_API_URL` (default `http://127.0.0.1:8000`).
Backend first:

```bash
uvicorn app.main:app --reload
```

## Build

```bash
npm run build
```

## Demo identities

Removed — sign in with real accounts:

- HR/Admin: create via `python scripts/create_admin.py --name ... --email ...`, then log in with that email + password.
- Employee: `POST /auth/login` after registering (`POST /auth/register`, always EMPLOYEE).

Roles are resolved server-side; the UI cannot escalate them. The JWT is kept
in localStorage and sent as `Authorization: Bearer`.
