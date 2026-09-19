import { useState } from "react";
import { ApiError, askQuestion } from "../api/client.js";
import { EmptyState, ErrorBanner, Loading } from "./Status.jsx";

function formatRelevance(score) {
  const value = Number(score);
  if (!Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

function SourceCard({ source }) {
  return (
    <details className="source-card">
      <summary>Source: {source.document || "unknown"}</summary>
      <dl>
        <div>
          <dt>Document</dt>
          <dd>{source.document}</dd>
        </div>
        <div>
          <dt>Section</dt>
          <dd>{source.section || "Not specified"}</dd>
        </div>
        <div>
          <dt>Page</dt>
          <dd>{source.page ?? "Not specified"}</dd>
        </div>
        <div>
          <dt>Relevance</dt>
          <dd>{formatRelevance(source.relevance_score)}</dd>
        </div>
      </dl>
    </details>
  );
}

export default function ChatInterface({ heading = "HR Assistant" }) {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const send = async (event) => {
    event.preventDefault();
    const text = question.trim();
    if (!text || sending) return;
    setSending(true);
    setError("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setQuestion("");
    try {
      const result = await askQuestion(text);
      const answer =
        result.retrieved_context_count === 0 && !result.answer
          ? "No sufficiently relevant information was found in the approved HR documents."
          : result.answer;
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: answer,
          sources: result.sources || [],
          meta: {
            model: result.model,
            latency_ms: result.latency_ms,
            retrieved_context_count: result.retrieved_context_count,
          },
        },
      ]);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "The request failed.";
      setError(message);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Request failed: ${message}` },
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <section className="panel">
      <h2>{heading}</h2>
      <p className="muted">
        Grounded answers from approved HR documents only, with source citations.
      </p>
      <ErrorBanner message={error} onRetry={() => setError("")} />
      <div className="chat-log" aria-live="polite">
        {messages.length === 0 && (
          <EmptyState
            title="No questions yet."
            hint="Ask about leave, remote work, or the code of conduct."
          />
        )}
        {messages.map((msg, index) => (
          <div key={index} className={`chat-message ${msg.role}`}>
            <p className="chat-text">{msg.content}</p>
            {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
              <div className="sources">
                <h4>Sources</h4>
                {msg.sources.map((source, i) => (
                  <SourceCard key={i} source={source} />
                ))}
              </div>
            )}
            {msg.role === "assistant" && msg.meta && (
              <p className="meta">
                Model {msg.meta.model} · {msg.meta.retrieved_context_count} context
                chunk(s) · {msg.meta.latency_ms} ms
              </p>
            )}
          </div>
        ))}
        {sending && <Loading text="Retrieving documents and generating an answer…" />}
      </div>
      <form className="chat-form" onSubmit={send}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about leave, remote work, code of conduct…"
          aria-label="Question"
          maxLength={500}
        />
        <button type="submit" className="btn btn-primary" disabled={sending || !question.trim()}>
          {sending ? "Asking…" : "Ask"}
        </button>
      </form>
    </section>
  );
}
