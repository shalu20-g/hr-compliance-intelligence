import { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  ApiError,
  getApiToken,
  getMe,
  loginRequest,
  logoutRequest,
  setApiToken,
} from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState("");
  const [restoring, setRestoring] = useState(true);

  const refreshUser = useCallback(async () => {
    const me = await getMe();
    setUser(me);
    return me;
  }, []);

  // Restore a persisted session once on startup.
  useEffect(() => {
    if (!getApiToken()) {
      setRestoring(false);
      return;
    }
    refreshUser()
      .catch(() => {
        setApiToken("");
        setUser(null);
      })
      .finally(() => setRestoring(false));
  }, [refreshUser]);

  const login = useCallback(
    async (email, password) => {
      const cleanEmail = String(email || "").trim();
      if (!cleanEmail || !password) {
        throw new Error("Enter your email and password to sign in.");
      }
      setAuthLoading(true);
      setAuthError("");
      try {
        const data = await loginRequest(cleanEmail, password);
        setApiToken(data.access_token);
        return await refreshUser();
      } catch (err) {
        setApiToken("");
        setUser(null);
        const message =
          err instanceof ApiError ? err.message : "Sign-in failed.";
        setAuthError(message);
        throw err;
      } finally {
        setAuthLoading(false);
      }
    },
    [refreshUser]
  );

  const logout = useCallback(async () => {
    try {
      if (getApiToken()) await logoutRequest();
    } catch {
      /* backend logout is best-effort; token is dropped regardless */
    }
    setApiToken("");
    setUser(null);
    setAuthError("");
  }, []);

  const value = {
    user,
    role: user ? user.role : "",
    isHr: user ? user.role === "HR_ADMIN" : false,
    isAuthenticated: Boolean(user),
    restoring,
    authLoading,
    authError,
    login,
    logout,
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
