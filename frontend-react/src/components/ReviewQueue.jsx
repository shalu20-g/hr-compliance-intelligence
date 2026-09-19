import { useCallback, useEffect, useState } from "react";
import { ApiError, approveReview, listReviews, rejectReview } from "../api/client.js";
import { EmptyState, ErrorBanner, Loading } from "./Status.jsx";

export default function ReviewQueue({ status, title, hint, actionable = false }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listReviews(status);
      setItems(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load reviews.");
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    load();
  }, [load]);

  const decide = async (reviewId, action) => {
    setBusyId(reviewId + action);
    setError("");
    try {
      if (action === "approve") {
        await approveReview(reviewId);
      } else {
        await rejectReview(reviewId);
      }
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Decision failed.");
    } finally {
      setBusyId("");
    }
  };

  return (
    <section className="panel">
      <h2>{title}</h2>
      {hint && <p className="muted">{hint}</p>}
      <ErrorBanner message={error} onRetry={load} />
      {loading ? (
        <Loading text="Loading review queue…" />
      ) : items.length === 0 ? (
        <EmptyState title={`No ${status} documents.`} hint={hint} />
      ) : (
        <ul className="review-list">
          {items.map((item) => (
            <li key={item.review_id} className="review-item">
              <div className="review-main">
                <strong>{item.filename}</strong>
                <span className={`badge ${item.status}`}>{item.status}</span>
                <p className="muted">{item.reason}</p>
                <p className="meta">
                  {item.review_id} · by {item.uploaded_by}
                </p>
              </div>
              {actionable && item.status === "pending" && (
                <div className="review-actions">
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={busyId !== ""}
                    onClick={() => decide(item.review_id, "approve")}
                  >
                    {busyId === item.review_id + "approve" ? "Approving…" : "Approve & index"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={busyId !== ""}
                    onClick={() => decide(item.review_id, "reject")}
                  >
                    {busyId === item.review_id + "reject" ? "Rejecting…" : "Reject"}
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
