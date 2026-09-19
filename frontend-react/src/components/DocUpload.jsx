import { useState } from "react";
import { ApiError, employeeSummarize, hrUploadDocument } from "../api/client.js";
import { ErrorBanner, Loading } from "./Status.jsx";

const ACCEPT = ".txt,.pdf,.docx";

/* HR company-document upload: staged into Pending Review, never auto-indexed. */
export function CompanyDocUpload({ onStaged }) {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const submit = async () => {
    if (!file || busy) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const record = await hrUploadDocument(file);
      setResult(record);
      if (onStaged) onStaged(record);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel">
      <h2>Upload Company Document</h2>
      <p className="muted">
        HR/Admin only. Files enter <strong>Pending Review</strong> first and are
        indexed only after approval. Personal or unrelated files are rejected.
      </p>
      <ErrorBanner message={error} onRetry={() => setError("")} />
      <div className="upload-row">
        <input
          type="file"
          accept={ACCEPT}
          onChange={(e) => setFile(e.target.files ? e.target.files[0] : null)}
          aria-label="Company HR document"
        />
        <button
          type="button"
          className="btn btn-primary"
          onClick={submit}
          disabled={!file || busy}
        >
          {busy ? "Submitting…" : "Submit for review"}
        </button>
      </div>
      {busy && <Loading text="Validating and staging for review…" />}
      {result && (
        <div className="result-card">
          <p>
            Staged <strong>{result.filename}</strong> as{" "}
            <strong>{result.status}</strong>.
          </p>
          <p className="muted">{result.reason}</p>
        </div>
      )}
    </section>
  );
}

/* Employee personal-document analysis: never touches the shared knowledge base. */
export function PersonalDocUpload({ onAnalysed }) {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const submit = async () => {
    if (!file || busy) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const analysis = await employeeSummarize(file);
      setResult(analysis);
      if (onAnalysed) onAnalysed(analysis);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Analysis failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel">
      <h2>Upload My Document</h2>
      <p className="muted">
        Your file is analysed privately. It is <strong>never</strong> added to
        the shared HR knowledge base.
      </p>
      <ErrorBanner message={error} onRetry={() => setError("")} />
      <div className="upload-row">
        <input
          type="file"
          accept={ACCEPT}
          onChange={(e) => setFile(e.target.files ? e.target.files[0] : null)}
          aria-label="Personal document"
        />
        <button
          type="button"
          className="btn btn-primary"
          onClick={submit}
          disabled={!file || busy}
        >
          {busy ? "Analysing…" : "Analyse (no indexing)"}
        </button>
      </div>
      {busy && <Loading text="Analysing privately…" />}
      {result && (
        <div className="result-card">
          <h3>Summary</h3>
          <p className="pre-wrap">{result.summary}</p>
          <p className="muted">{result.note}</p>
        </div>
      )}
    </section>
  );
}
