import { useEffect, useState } from "react";
import { getHealth } from "./api/client.js";
import { AuthProvider, useAuth } from "./context/AuthContext.jsx";
import { Loading } from "./components/Status.jsx";
import EmployeeDashboard from "./pages/EmployeeDashboard.jsx";
import HRDashboard from "./pages/HRDashboard.jsx";
import Login from "./pages/Login.jsx";

function HealthBanner() {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then((data) => {
        if (!cancelled) setHealth(data);
      })
      .catch(() => {
        if (!cancelled) setHealth(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!health) return null;
  const components = health.components || {};
  return (
    <p className="health-line" aria-live="polite">
      Backend {health.status} · {components.documents_indexed ?? 0} document(s) ·{" "}
      {components.chunks_indexed ?? 0} chunk(s) · {health.version}
    </p>
  );
}

function Shell() {
  const { isAuthenticated, isHr, user, role, logout, restoring } = useAuth();

  if (restoring) {
    return (
      <div className="app">
        <main className="main">
          <Loading text="Restoring session…" />
        </main>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="app">
        <header className="topbar">
          <strong>HR Compliance Intelligence</strong>
        </header>
        <main className="main">
          <Login />
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <strong>HR Compliance Intelligence</strong>
          <span className="muted">
            {" "}
            · {isHr ? "HR/Admin Dashboard" : "Employee Dashboard"}
          </span>
        </div>
        <div className="userbox">
          <span>
            {user.email} <span className={`badge ${role}`}>{role}</span>
          </span>
          <button type="button" className="btn btn-secondary" onClick={logout}>
            Logout
          </button>
        </div>
      </header>
      <main className="main">
        <HealthBanner />
        {isHr ? <HRDashboard /> : <EmployeeDashboard />}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
