import { useState } from "react";
import ChatInterface from "../components/ChatInterface.jsx";
import DocList from "../components/DocList.jsx";
import { CompanyDocUpload } from "../components/DocUpload.jsx";
import ReviewQueue from "../components/ReviewQueue.jsx";

const TABS = [
  "HR Assistant",
  "Upload Company Document",
  "Pending Reviews",
  "Approved Documents",
  "Rejected Documents",
];

export default function HRDashboard() {
  const [tab, setTab] = useState(TABS[0]);
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div>
      <nav className="tabs" aria-label="HR sections">
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
      {tab === "HR Assistant" && <ChatInterface heading="HR Assistant" />}
      {tab === "Upload Company Document" && (
        <CompanyDocUpload onStaged={() => setRefreshKey((k) => k + 1)} />
      )}
      {tab === "Pending Reviews" && (
        <div key={refreshKey}>
          <ReviewQueue
            status="pending"
            title="Pending Reviews"
            hint="Uncertain uploads awaiting an HR decision. Not in ChromaDB."
            actionable
          />
        </div>
      )}
      {tab === "Approved Documents" && (
        <div key={refreshKey}>
          <DocList allowDelete />
        </div>
      )}
      {tab === "Rejected Documents" && (
        <ReviewQueue
          status="rejected"
          title="Rejected Documents"
          hint="Quarantined files. Never indexed, never used for answers."
        />
      )}
    </div>
  );
}
