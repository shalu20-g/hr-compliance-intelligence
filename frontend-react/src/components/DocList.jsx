import { useCallback, useEffect, useState } from "react";
import { ApiError, deleteDocument, listDocuments, summarizeDocument } from "../api/client.js";
import { EmptyState, ErrorBanner, Loading } from "./Status.jsx";

/* Indexed shared documents with on-demand grounded summaries.
 * When `allowDelete` is set (HR), a delete action is offered. */
export default function DocList({ allowDelete = false }) {
  const [docs, setDocs] = useState([]);
  const [totals, setTotals] = useState({ total_documents: 0, total_chunks: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [summaries, setSummaries] = useState({});
  const [busyName, setBusyName] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const body = await listDocuments();
      setDocs(body.documents || []);
      setTotals({
        total_documents: body.total_documents || 0,
        total_chunks: body.total_chunks || 0,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load documents.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const summarize = async (filename) => {
    setBusyName(filename);
    setError("");
    try {
      const result = await summarizeDocument(filename);
      setSummaries((prev) => ({ ...prev, [filename]: result.summary }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Summary failed.");
    } finally {
      setBusyName("");
    }
  };

  const remove = async (filename) => {
    setBusyName(filename);
    setError("");
    try {
      await deleteDocument(filename);
      setSummaries((prev) => {
        const next = { ...prev };
        delete next[filename];
        return next;
      });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed.");
    } finally {
      setBusyName("");
    }
  };

  return (
    <section className="panel">
      <h2>Approved Documents</h2>
      <p className="muted">
        {totals.total_documents} document(s) · {totals.total_chunks} chunk(s) indexed
        in the shared knowledge base.
      </p>
      <ErrorBanner message={error} onRetry={load} />
      {loading ? (
        <Loading text="Loading documents…" />
      ) : docs.length === 0 ? (
        <EmptyState
          title="No approved documents indexed yet."
          hint="HR can stage a company document and approve it from Pending Reviews."
        />
      ) : (
        <ul className="doc-list">
          {docs.map((doc) => (
            <li key={doc.filename} className="doc-item">
              <div className="doc-main">
                <strong>{doc.filename}</strong>
                <span className="meta">
                  {doc.chunk_count} chunk(s)
                  {doc.ingested_at ? ` · indexed ${doc.ingested_at}` : ""}
                </span>
              </div>
              <div className="doc-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={busyName === doc.filename}
                  onClick={() => summarize(doc.filename)}
                >
                  {busyName === doc.filename ? "Summarising…" : "Generate summary"}
                </button>
                {allowDelete && (
                  <button
                    type="button"
                    className="btn btn-danger"
                    disabled={busyName === doc.filename}
                    onClick={() => remove(doc.filename)}
                  >
                    Delete
                  </button>
                )}
              </div>
              {summaries[doc.filename] && (
                <p className="pre-wrap summary">{summaries[doc.filename]}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
