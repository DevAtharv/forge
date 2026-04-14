import React, { createContext, useContext, useState, useEffect } from "react";
import { fetchJson } from "./api";

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [user, setUser] = useState(null);
  const [authEnabled, setAuthEnabled] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function init() {
      try {
        const config = await fetchJson("/api/client-config");
        setAuthEnabled(Boolean(config.auth_enabled));
      } catch (err) {
        setAuthEnabled(false);
      }

      const stored = localStorage.getItem("forge_session");
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          if (parsed.session && parsed.session.access_token) {
            const payload = await fetchJson("/api/auth/session", {
              headers: { Authorization: `Bearer ${parsed.session.access_token}` },
            });
            saveSession(parsed.session, payload.user);
          }
        } catch {
          clearSession();
        }
      }
      setLoading(false);
    }
    init();
  }, []);

  const saveSession = (newSession, newUser) => {
    setSession(newSession);
    setUser(newUser);
    localStorage.setItem(
      "forge_session",
      JSON.stringify({ session: newSession, user: newUser })
    );
  };

  const clearSession = () => {
    setSession(null);
    setUser(null);
    localStorage.removeItem("forge_session");
  };

  const signIn = async (email, password) => {
    const payload = await fetchJson("/api/auth/signin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (payload.session) {
      saveSession(payload.session, payload.user);
    }
    return payload;
  };

  const signUp = async (email, password) => {
    const payload = await fetchJson("/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (payload.session) {
      saveSession(payload.session, payload.user);
    }
    return payload;
  };

  const signOut = async () => {
    if (session) {
      try {
        await fetchJson("/api/auth/signout", {
          method: "POST",
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
      } catch {}
    }
    clearSession();
  };

  return (
    <AuthContext.Provider
      value={{
        session,
        user,
        authEnabled,
        loading,
        saveSession,
        clearSession,
        signIn,
        signUp,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
