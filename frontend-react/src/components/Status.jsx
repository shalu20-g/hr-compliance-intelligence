export function Loading({ text = "Loading…" }) {
  return (
    <div className="status-card loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{text}</span>
    </div>
  );
}

export function ErrorBanner({ message, onRetry }) {
  if (!message) return null;
  return (
    <div className="status-card error" role="alert">
      <strong>Something went wrong.</strong>
      <p>{message}</p>
      {onRetry && (
        <button type="button" className="btn btn-secondary" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, hint }) {
  return (
    <div className="status-card empty">
      <strong>{title || "Nothing here yet."}</strong>
      {hint && <p>{hint}</p>}
    </div>
  );
}
