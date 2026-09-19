/* REST client for the existing FastAPI backend.
 *
 * Authentication is email + password (JWT bearer tokens):
 * - POST /auth/login {email, password} -> {access_token, token_type}.
 * - POST /auth/register {name, email, password} -> user (always EMPLOYEE).
 * - POST /auth/logout -> {status} (client also discards its token).
 * - GET /auth/me -> {id, name, email, role} with role HR_ADMIN | EMPLOYEE.
 * The token is sent as `Authorization: Bearer <token>` on every call and
 * the role is always resolved server-side from the users table.
 *
 * Other contracts mirror the backend exactly:
 * - POST /chat {question} -> {answer, sources[], retrieved_context_count,
 *   model, latency_ms, retrieved_chunks[]}.
 * - GET /documents (HR only) -> {documents[{filename, chunk_count,
 *   ingested_at}], total_documents, total_chunks}.
 * - POST /documents/hr/upload (multipart `file`, HR only) -> 202 review
 *   record {review_id, filename, status, reason, category, confidence, ...}.
 * - GET /documents/review?status=pending|approved|rejected (HR only) -> list.
 * - POST /documents/review/{id}/approve|reject (HR only) -> record.
 * - DELETE /documents/{name} (HR only) -> {deleted, chunks_removed}.
 * - POST /documents/{name}/summary (HR only) ->
 *   {document, chunk_count, summary, model}.
 * - POST /employee/summarize (multipart `file`) ->
 *   {filename, summary, char_count, indexed, note}.
 * - GET /health -> {status, app_name, version, components}.
 *
 * No RAG/LangChain logic lives here — the React app only calls the API.
 */

const API_BASE =
  (typeof import.meta !== "undefined" &&
    import.meta.env &&
    import.meta.env.VITE_API_URL) ||
  "http://127.0.0.1:8000";

const TOKEN_KEY = "hrbot.token";

export function getApiToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function setApiToken(token) {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    /* storage unavailable — session-only */
  }
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message || `Request failed (HTTP ${status})`);
    this.name = "ApiError";
    this.status = status;
  }
}

function extractDetail(payload, status) {
  if (payload == null) return `Request failed (HTTP ${status})`;
  if (typeof payload === "string") return payload;
  const detail = payload.detail !== undefined ? payload.detail : payload;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const message = detail.message || detail.detail;
    let base = message ? String(message) : "The request failed.";
    const failures = detail.failures;
    if (Array.isArray(failures) && failures.length > 0) {
      const names = failures
        .map((f) => (f && f.filename ? f.filename : null))
        .filter(Boolean)
        .join(", ");
      if (names) base += ` Affected file(s): ${names}.`;
      const first = failures.find((f) => f && f.error);
      if (first) base += ` ${first.error}`;
    }
    return base;
  }
  return `Request failed (HTTP ${status})`;
}

export async function apiFetch(path, { method = "GET", json, formFile, params } = {}) {
  const url = new URL(`${API_BASE}/${String(path).replace(/^\//, "")}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }
  const headers = {};
  const token = getApiToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let body;
  if (formFile) {
    const form = new FormData();
    form.append("file", formFile);
    body = form; // browser sets the multipart boundary automatically
  } else if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  }

  const response = await fetch(url.toString(), { method, headers, body });
  if (response.status === 401) {
    // Session is invalid/expired: drop it so the app returns to login.
    setApiToken("");
  }
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    throw new ApiError(response.status, extractDetail(payload, response.status));
  }
  return payload;
}

// --- Auth endpoints ---------------------------------------------------

export const loginRequest = (email, password) =>
  apiFetch("/auth/login", { method: "POST", json: { email, password } });

export const registerRequest = (name, email, password) =>
  apiFetch("/auth/register", {
    method: "POST",
    json: { name, email, password },
  });

export const logoutRequest = () => apiFetch("/auth/logout", { method: "POST" });

export const getMe = () => apiFetch("/auth/me");

// --- Endpoint helpers -------------------------------------------------

export const askQuestion = (question) =>
  apiFetch("/chat", { method: "POST", json: { question } });

export const listDocuments = () => apiFetch("/documents");

export const hrUploadDocument = (file) =>
  apiFetch("/documents/hr/upload", { method: "POST", formFile: file });

export const listReviews = (status) =>
  apiFetch("/documents/review", {
    params: status ? { status } : undefined,
  });

export const approveReview = (reviewId) =>
  apiFetch(`/documents/review/${encodeURIComponent(reviewId)}/approve`, {
    method: "POST",
  });

export const rejectReview = (reviewId) =>
  apiFetch(`/documents/review/${encodeURIComponent(reviewId)}/reject`, {
    method: "POST",
  });

export const deleteDocument = (documentName) =>
  apiFetch(`/documents/${encodeURIComponent(documentName)}`, {
    method: "DELETE",
  });

export const summarizeDocument = (documentName) =>
  apiFetch(`/documents/${encodeURIComponent(documentName)}/summary`, {
    method: "POST",
  });

export const employeeSummarize = (file) =>
  apiFetch("/employee/summarize", { method: "POST", formFile: file });

export const getHealth = () => apiFetch("/health");
