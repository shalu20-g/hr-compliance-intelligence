import { useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { ApiError, registerRequest } from "../api/client.js";
import { ErrorBanner, Loading } from "../components/Status.jsx";

function isValidEmail(value) {
  const clean = String(value || "").trim().toLowerCase();
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(clean);
}

export default function Login() {
  const { login, authLoading, authError } = useAuth();
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState("");
  const [notice, setNotice] = useState("");
  const [registering, setRegistering] = useState(false);

  const switchMode = (next) => {
    setMode(next);
    setLocalError("");
    setNotice("");
  };

  const submitLogin = async (event) => {
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

  const submitRegister = async (event) => {
    event.preventDefault();
    setLocalError("");
    setNotice("");
    if (!name.trim()) {
      setLocalError("Enter your name.");
      return;
    }
    if (!isValidEmail(email)) {
      setLocalError("Enter a valid email address.");
      return;
    }
    if (password.length < 8) {
      setLocalError("Password must be at least 8 characters.");
      return;
    }
    setRegistering(true);
    try {
      await registerRequest(name.trim(), email.trim(), password);
      setNotice("Account created as EMPLOYEE. You can now sign in.");
      setPassword("");
      setMode("login");
    } catch (err) {
      setLocalError(
        err instanceof ApiError ? err.message : "Registration failed."
      );
    } finally {
      setRegistering(false);
    }
  };

  const busy = authLoading || registering;

  return (
    <div className="login-wrap">
      <section className="panel login-card">
        <h1>HR Compliance Intelligence</h1>
        <p className="muted">
          {mode === "login"
            ? "Sign in with your email and password. Your role (HR_ADMIN or EMPLOYEE) is resolved by the backend and cannot be changed here."
            : "Create your employee account. New accounts always receive the EMPLOYEE role."}
        </p>
        <ErrorBanner message={localError || authError} />
        {notice && (
          <div className="status-card success" role="status">
            {notice}
          </div>
        )}
        {mode === "login" ? (
          <form onSubmit={submitLogin} className="login-form">
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
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {authLoading ? "Signing in…" : "Sign in"}
            </button>
          </form>
        ) : (
          <form onSubmit={submitRegister} className="login-form">
            <label>
              Name
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your full name"
                aria-label="Name"
                autoComplete="name"
                maxLength={120}
              />
            </label>
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
                placeholder="At least 8 characters"
                aria-label="Password"
                autoComplete="new-password"
              />
            </label>
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {registering ? "Creating account…" : "Create account"}
            </button>
          </form>
        )}
        {authLoading && mode === "login" && (
          <Loading text="Verifying with the backend…" />
        )}
        <div className="quick-signin">
          {mode === "login" ? (
            <>
              <span className="muted">No account yet?</span>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => switchMode("register")}
                disabled={busy}
              >
                Register
              </button>
            </>
          ) : (
            <>
              <span className="muted">Already have an account?</span>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => switchMode("login")}
                disabled={busy}
              >
                Back to Login
              </button>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
