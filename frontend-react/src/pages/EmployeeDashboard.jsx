import { useState } from "react";
import ChatInterface from "../components/ChatInterface.jsx";
import { PersonalDocUpload } from "../components/DocUpload.jsx";
import { EmptyState } from "../components/Status.jsx";

const TABS = ["Ask HR Assistant", "Upload My Document", "My Document Summary"];

export default function EmployeeDashboard() {
  const [tab, setTab] = useState(TABS[0]);
  const [personal, setPersonal] = useState(null);

  return (
    <div>
      <nav className="tabs" aria-label="Employee sections">
        {TABS.map((name) => (
          <button
            key={name}
            type="button"
            className={`tab${tab === name ? " active" : ""}`}
            onClick={() => setTab(name)}
          >
            {name}
          </button>
        ))}
      </nav>
      {tab === "Ask HR Assistant" && <ChatInterface heading="Ask HR Assistant" />}
      {tab === "Upload My Document" && <PersonalDocUpload onAnalysed={setPersonal} />}
      {tab === "My Document Summary" && (
        <section className="panel">
          <h2>My Document Summary</h2>
          <p className="muted">
            Summary of your own personal document. It was never added to the
            shared HR knowledge base.
          </p>
          {personal ? (
            <div>
              <p className="pre-wrap">{personal.summary}</p>
              <p className="muted">{personal.note}</p>
            </div>
          ) : (
            <EmptyState
              title="No personal summary yet."
              hint="Go to Upload My Document and analyse a file first."
            />
          )}
        </section>
      )}
    </div>
  );
}
