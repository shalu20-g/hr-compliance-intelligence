import { useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { ApiError } from "../api/client.js";
import { ErrorBanner, Loading } from "../components/Status.jsx";

export default function Login() {
  const { login, authLoading, authError } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    setLocalError("");
    try {
      await login(email, password);
    } catch (err) {
      if (!(err instanceof ApiError)) {
        setLocalError(err.message || "Sign-in failed.");
      }
    }
  };

  return (
    <div className="login-wrap">
      <section className="panel login-card">
        <h1>HR Compliance Intelligence</h1>
        <p className="muted">
          Sign in with your email and password. Your role (HR_ADMIN or
          EMPLOYEE) is resolved by the backend and cannot be changed here.
        </p>
        <ErrorBanner message={localError || authError} />
        <form onSubmit={submit} className="login-form">
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              aria-label="Email"
              autoComplete="email"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Your password"
              aria-label="Password"
              autoComplete="current-password"
            />
          </label>
          <button type="submit" className="btn btn-primary" disabled={authLoading}>
            {authLoading ? "Signing in…" : "Sign in"}
          </button>
        </form>
        {authLoading && <Loading text="Verifying with the backend…" />}
      </section>
    </div>
  );
}
