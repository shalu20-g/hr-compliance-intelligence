"""Streamlit frontend for the Enterprise HR Compliance Bot.

Role-aware "HR Compliance Intelligence" UI with email + password login
(JWT bearer token). The backend resolves the role server-side from the users
table; the UI cannot escalate it.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import requests
import streamlit as st

st.set_page_config(
    page_title="HR Compliance Intelligence",
    page_icon=":briefcase:",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = st.sidebar.text_input("API base URL", value="http://127.0.0.1:8000")

# --- Authenticated session state (login UI is rendered after the API
# helpers below, once build_api_url is defined). No demo identities: the
# user logs in with email + password and the backend returns the role. ---
if "auth_token" not in st.session_state:
    st.session_state.auth_token = ""
if "auth_user" not in st.session_state:
    st.session_state.auth_user = {}


def _auth_headers() -> dict:
    token = st.session_state.auth_token
    return {"Authorization": f"Bearer {token}"} if token else {}


st.title("HR Compliance Intelligence")
st.caption("AI-powered HR policy analysis and document intelligence")


# ------------------------------------------------------------------ #
# API helpers
# ------------------------------------------------------------------ #
class FrontendAPIError(Exception):
    """A user-presentable error raised when the backend rejects a request."""


def build_api_url(path: str) -> str:
    base = API_URL.rstrip("/")
    return f"{base}/{path.lstrip('/')}"


def api_error_text(response: requests.Response) -> str:
    """Extract a clean, user-presentable error message from any API response."""
    try:
        payload = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"

    if isinstance(payload, dict):
        detail = payload.get("detail", payload)
        if isinstance(detail, str):
            return detail
        if isinstance(detail, dict):
            message = detail.get("message") or detail.get("detail")
            base = str(message) if message else "The request failed."
            failures = detail.get("failures")
            if isinstance(failures, list) and failures:
                names = ", ".join(
                    f.get("filename", "?")
                    for f in failures
                    if isinstance(f, dict)
                )
                if names:
                    base = f"{base} Affected file(s): {names}."
                errors = [
                    f.get("error")
                    for f in failures
                    if isinstance(f, dict) and f.get("error")
                ]
                if errors:
                    base = f"{base} {errors[0]}"
            return base
        return str(detail) if detail else f"HTTP {response.status_code}"

    if isinstance(payload, list):
        return "; ".join(str(item) for item in payload)
    return f"HTTP {response.status_code}"


def call_api(
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    files: dict | None = None,
    params: dict | None = None,
    timeout: int = 60,
) -> dict | list:
    """Perform an authenticated request (JWT bearer) or raise FrontendAPIError."""
    try:
        response = requests.request(
            method,
            build_api_url(path),
            json=json_body,
            files=files,
            params=params,
            headers=HEADERS,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise FrontendAPIError(f"Cannot reach the API at {API_URL}: {exc}") from exc
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise FrontendAPIError(api_error_text(response)) from exc
    try:
        return response.json()
    except ValueError as exc:
        raise FrontendAPIError(
            "The API returned an unexpected response."
        ) from exc


@st.cache_data(ttl=10, show_spinner=False)
def get_health(url_base: str) -> dict | None:
    """Fetch /health (cached briefly); None when the backend is unreachable."""
    try:
        response = requests.get(f"{url_base.rstrip('/')}/health", timeout=5)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException:
        pass
    return None


def list_documents() -> dict:
    return call_api("GET", "documents", timeout=10)


def hr_upload_document(uploaded_file) -> dict:
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream",
        )
    }
    return call_api("POST", "documents/hr/upload", files=files, timeout=120)


def list_reviews(status: str | None = None) -> list:
    params = {"status": status} if status else None
    data = call_api("GET", "documents/review", params=params, timeout=15)
    return data if isinstance(data, list) else []


def approve_review(review_id: str) -> dict:
    return call_api("POST", f"documents/review/{quote(review_id, safe='')}/approve", timeout=120)


def reject_review(review_id: str) -> dict:
    return call_api("POST", f"documents/review/{quote(review_id, safe='')}/reject", timeout=30)


def employee_summarize(uploaded_file) -> dict:
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream",
        )
    }
    return call_api("POST", "employee/summarize", files=files, timeout=120)


def trigger_ingest() -> dict:
    return call_api("POST", "documents/ingest", timeout=120)


def generate_document_summary(document_name: str) -> dict:
    return call_api(
        "POST",
        f"documents/{quote(document_name, safe='')}/summary",
        timeout=120,
    )


def delete_document(document_name: str) -> dict:
    return call_api(
        "DELETE",
        f"documents/{quote(document_name, safe='')}",
        timeout=30,
    )


def ask_question(question: str) -> dict:
    return call_api("POST", "chat", json_body={"question": question}, timeout=60)


def doc_file_type(filename: str) -> str:
    return (Path(filename).suffix.lstrip(".") or "unknown").upper()


# ------------------------------------------------------------------ #
# Email + password login (JWT). No demo identities.
# ------------------------------------------------------------------ #
st.sidebar.subheader("Sign in")
if not st.session_state.auth_token:
    login_email = st.sidebar.text_input("Email", key="login_email")
    login_password = st.sidebar.text_input(
        "Password", type="password", key="login_password"
    )
    if st.sidebar.button("Log in", key="login_submit"):
        login_resp = None
        try:
            login_resp = requests.post(
                build_api_url("auth/login"),
                json={"email": login_email, "password": login_password},
                timeout=10,
            )
            login_resp.raise_for_status()
        except requests.RequestException as exc:
            detail = ""
            try:
                detail = login_resp.json().get("detail", "") if login_resp is not None else ""
            except Exception:
                detail = str(exc)
            st.sidebar.error(f"Login failed: {detail or exc}")
            st.stop()
        st.session_state.auth_token = login_resp.json().get("access_token", "")
        st.rerun()
    st.info("Log in with your email and password to continue.")
    st.stop()
else:
    try:
        me_resp = requests.get(
            build_api_url("auth/me"), headers=_auth_headers(), timeout=10
        )
        me_resp.raise_for_status()
        st.session_state.auth_user = me_resp.json()
    except requests.RequestException:
        st.sidebar.error("Session expired. Please log in again.")
        st.session_state.auth_token = ""
        st.session_state.auth_user = {}
        st.rerun()
    if st.sidebar.button("Logout", key="logout"):
        try:
            requests.post(
                build_api_url("auth/logout"), headers=_auth_headers(), timeout=10
            )
        except requests.RequestException:
            pass
        st.session_state.auth_token = ""
        st.session_state.auth_user = {}
        st.rerun()

USER_EMAIL = st.session_state.auth_user.get("email", "")
HEADERS = _auth_headers()


# ------------------------------------------------------------------ #
# Startup health gate + role banner
# ------------------------------------------------------------------ #
health = get_health(API_URL)
if health is None:
    st.error(
        f"Cannot reach the API at {API_URL}. "
        "Make sure the backend is running with `uvicorn app.main:app --reload`."
    )
    st.stop()

me = st.session_state.auth_user
role = me.get("role", "unknown")
is_hr = role == "HR_ADMIN"

components = health.get("components", {})

if "nav_go" in st.session_state:
    st.session_state.navigation = st.session_state.pop("nav_go")

st.sidebar.success("Backend connected")
st.sidebar.markdown(f"**Signed in as:** `{USER_EMAIL}`")
st.sidebar.markdown(
    "**Role (server-resolved):** "
    + (":green[HR/Admin]" if is_hr else ":blue[Employee]")
)
st.sidebar.caption("Roles are assigned by the backend and cannot be changed here.")

if is_hr:
    PAGES = [
        "Dashboard",
        "Upload Company HR Document",
        "Pending Documents",
        "Approved Documents",
        "Rejected Documents",
        "Compliance AI",
        "System Status",
    ]
else:
    PAGES = [
        "Ask HR Assistant",
        "Upload My Document",
        "Get Summary",
        "System Status",
    ]

page = st.sidebar.radio("Navigation", PAGES, key="navigation")

with st.sidebar:
    st.divider()
    st.markdown("**Live system snapshot**")
    st.markdown(
        "ChromaDB: "
        + (
            ":green[available]"
            if components.get("chroma_available")
            else ":red[unavailable]"
        )
    )
    st.markdown(
        "Documents indexed: "
        f":blue[{components.get('documents_indexed', 0)}]"
    )
    st.markdown(
        "Chunks indexed: :blue[{count}]".format(
            count=components.get("chunks_indexed", 0)
        )
    )


def navigate(target: str) -> None:
    st.session_state.nav_go = target
    st.rerun()


# ------------------------------------------------------------------ #
# Shared renderers
# ------------------------------------------------------------------ #
def render_review_table(items: list, *, show_actions: bool = False) -> None:
    if not items:
        st.info("Nothing here.")
        return
    rows = [
        {
            "Review ID": r.get("review_id"),
            "Filename": r.get("filename"),
            "Status": r.get("status"),
            "Reason": (r.get("reason") or "")[:160],
            "By": r.get("uploaded_by"),
        }
        for r in items
    ]
    st.dataframe(rows, width="stretch", hide_index=True)
    if show_actions:
        for r in items:
            rid = r.get("review_id", "")
            with st.expander(f"{r.get('filename')} — {rid}"):
                st.markdown(f"**Status:** {r.get('status')}")
                st.markdown(f"**Reason:** {r.get('reason')}")
                col_a, col_b = st.columns(2)
                if col_a.button("Approve & index", key=f"approve_{rid}"):
                    try:
                        result = approve_review(rid)
                    except FrontendAPIError as exc:
                        st.error(str(exc))
                    else:
                        st.success(
                            f"Approved '{result.get('filename')}' "
                            f"({result.get('chunks_added', 0)} chunk(s) indexed)."
                        )
                        st.rerun()
                if col_b.button("Reject", key=f"reject_{rid}"):
                    try:
                        reject_review(rid)
                    except FrontendAPIError as exc:
                        st.error(str(exc))
                    else:
                        st.warning("Rejected and quarantined (not in ChromaDB).")
                        st.rerun()


def render_dashboard(health_info: dict) -> None:
    comps = health_info.get("components", {})
    st.subheader("Dashboard")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Documents indexed", comps.get("documents_indexed", 0))
    col_b.metric("Chunks indexed", comps.get("chunks_indexed", 0))
    col_c.metric(
        "ChromaDB", "Available" if comps.get("chroma_available") else "Unavailable"
    )
    st.info(
        "**Safety model:** HR uploads enter Pending Review first; only approved "
        "documents are indexed. Heuristic classification assists but never "
        "replaces backend authorization."
    )


def render_hr_upload() -> None:
    st.subheader("Upload Company HR Document")
    st.caption(
        "HR/Admin only. Files enter **Pending Review** first and are indexed "
        "only after approval. Irrelevant/personal files are rejected or held."
    )
    uploaded = st.file_uploader(
        "Choose a company HR document", type=["txt", "pdf", "docx"], key="hr_uploader"
    )
    if uploaded is not None and st.button("Submit for review", key="hr_submit"):
        with st.spinner("Validating and staging for review..."):
            try:
                record = hr_upload_document(uploaded)
            except FrontendAPIError as exc:
                st.error(str(exc))
            else:
                st.success(
                    f"Staged '{record.get('filename')}' as "
                    f"**{record.get('status')}**. Reason: {record.get('reason')}"
                )


def render_pending() -> None:
    st.subheader("Pending Documents")
    st.caption("Uncertain uploads awaiting an HR decision. Not in ChromaDB.")
    try:
        items = list_reviews("pending")
    except FrontendAPIError as exc:
        st.error(str(exc))
        return
    render_review_table(items, show_actions=True)


def render_approved() -> None:
    st.subheader("Approved Documents")
    st.caption("Approved review records. Only these are indexed into ChromaDB.")
    try:
        items = list_reviews("approved")
    except FrontendAPIError as exc:
        st.error(str(exc))
        return
    render_review_table(items)
    st.divider()
    st.markdown("### Indexed in ChromaDB")
    try:
        body = list_documents()
    except FrontendAPIError as exc:
        st.error(str(exc))
        return
    for doc in body.get("documents", []):
        st.markdown(f"- {doc['filename']} ({doc.get('chunk_count', 0)} chunks)")


def render_rejected() -> None:
    st.subheader("Rejected Documents")
    st.caption("Quarantined files. Never indexed, never used for answers.")
    try:
        items = list_reviews("rejected")
    except FrontendAPIError as exc:
        st.error(str(exc))
        return
    render_review_table(items)


def render_source(source: dict) -> None:
    relevance = source.get("relevance_score", 0.0)
    try:
        relevance_pct = f"{float(relevance) * 100:.2f}%"
    except (TypeError, ValueError):
        relevance_pct = "—"
    with st.expander(f"Source: {source.get('document', 'unknown')}"):
        st.markdown(f"**Document:** {source.get('document')}")
        st.markdown(f"**Section:** {source.get('section') or 'Not specified'}")
        st.markdown(f"**Relevance:** {relevance_pct}")


def render_chat(title: str) -> None:
    st.subheader(title)
    st.info("Grounded answers from approved HR documents only, with citations.")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    question = st.chat_input("Ask about leave, remote work, code of conduct, ...")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Retrieving approved documents..."):
                try:
                    result = ask_question(question)
                except FrontendAPIError as exc:
                    st.error(str(exc))
                    st.session_state.messages.append(
                        {"role": "assistant", "content": f"Request failed: {exc}"}
                    )
                    st.stop()
            if result.get("retrieved_context_count", 0) == 0:
                st.warning("No sufficiently relevant information in approved documents.")
            else:
                st.markdown(result.get("answer", ""))
            for source in result.get("sources", []):
                render_source(source)
        st.session_state.messages.append(
            {"role": "assistant", "content": result.get("answer", "Insufficient information.")}
        )


def render_employee_upload() -> None:
    st.subheader("Upload My Document")
    st.caption(
        "Analyse a personal document. It is **never** added to the shared HR "
        "knowledge base and never affects anyone's answers."
    )
    uploaded = st.file_uploader(
        "Choose your document", type=["txt", "pdf", "docx"], key="emp_uploader"
    )
    if uploaded is not None and st.button("Analyse (no indexing)", key="emp_submit"):
        with st.spinner("Analysing privately..."):
            try:
                result = employee_summarize(uploaded)
            except FrontendAPIError as exc:
                st.error(str(exc))
            else:
                st.session_state.last_personal = result
                st.success("Analysed. Not indexed (see note below).")
    personal = st.session_state.get("last_personal")
    if personal:
        st.markdown(personal.get("summary", ""))
        st.caption(personal.get("note", ""))


def render_employee_summary() -> None:
    st.subheader("Get Summary")
    st.caption("Summaries of approved shared documents or your personal upload.")
    personal = st.session_state.get("last_personal")
    if personal:
        with st.expander("My personal document summary", expanded=True):
            st.markdown(personal.get("summary", ""))
            st.caption(personal.get("note", ""))
    st.markdown("### Shared document summary")
    try:
        body = list_documents()
    except FrontendAPIError as exc:
        st.error(str(exc))
        return
    names = [d["filename"] for d in body.get("documents", [])]
    if not names:
        st.info("No approved documents indexed yet.")
        return
    choice = st.selectbox("Document", names, key="emp_shared_choice")
    if st.button("Generate summary", key="emp_shared_summary"):
        try:
            result = generate_document_summary(choice)
        except FrontendAPIError as exc:
            st.error(str(exc))
        else:
            st.markdown(result.get("summary", ""))


def render_system_status(health_info: dict) -> None:
    comps = health_info.get("components", {})
    st.subheader("System Status")
    st.markdown(f"- ChromaDB: {comps.get('chroma_available')}")
    st.markdown(f"- Documents indexed: {comps.get('documents_indexed', 0)}")
    st.markdown(f"- Chunks indexed: {comps.get('chunks_indexed', 0)}")
    st.markdown(f"- LLM provider: {comps.get('llm_provider', '—')}")


# ------------------------------------------------------------------ #
# Page router
# ------------------------------------------------------------------ #
if "messages" not in st.session_state:
    st.session_state.messages = []
if "summaries" not in st.session_state:
    st.session_state.summaries = {}

if page == "Dashboard":
    render_dashboard(health)
elif page == "Upload Company HR Document":
    render_hr_upload()
elif page == "Pending Documents":
    render_pending()
elif page == "Approved Documents":
    render_approved()
elif page == "Rejected Documents":
    render_rejected()
elif page in ("Compliance AI", "Ask HR Assistant"):
    render_chat(page)
elif page == "Upload My Document":
    render_employee_upload()
elif page == "Get Summary":
    render_employee_summary()
elif page == "System Status":
    render_system_status(health)
