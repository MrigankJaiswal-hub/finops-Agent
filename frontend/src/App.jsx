// frontend/src/App.jsx
// Root component
import React, { useEffect, useRef } from "react";
import { Routes, Route } from "react-router-dom";
import { useAuth } from "react-oidc-context";

import Navbar from "./components/Navbar";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import AIInsights from "./pages/AIInsights";
import UploadPage from "./pages/UploadPage";
import Clients from "./pages/Clients";
import ErrorBoundary from "./components/ErrorBoundary";
import Actions from "./pages/Actions";
import AdminBudgets from "./pages/AdminBudgets";



// API helper token binder
import { setAuthToken, clearAuthToken } from "./utils/api";

/**
 * ENV CONFIG
 * - VITE_CLIENT_ID:         Cognito App Client ID
 * - VITE_OIDC_DOMAIN:       e.g. https://<your-domain>.auth.<region>.amazoncognito.com
 * - VITE_OIDC_LOGOUT_REDIRECT_URI: Where Cognito should redirect after logout (default: window.origin)
 */
const CLIENT_ID = import.meta.env.VITE_CLIENT_ID;
const OIDC_DOMAIN =
  import.meta.env.VITE_OIDC_DOMAIN ||
  "https://us-east-2_3hGBifjKi.auth.us-east-2.amazoncognito.com"; // fallback for dev
const LOGOUT_REDIRECT =
  import.meta.env.VITE_OIDC_LOGOUT_REDIRECT_URI || window.location.origin;

// ---------- Route guard ----------
function RequireAuth({ children }) {
  const auth = useAuth();

  // Auto-redirect to Hosted UI if not authenticated
  useEffect(() => {
    if (!auth.isLoading && !auth.isAuthenticated && !auth.error) {
      auth.signinRedirect();
    }
  }, [auth.isLoading, auth.isAuthenticated, auth.error, auth]);

  if (auth.isLoading) {
    return (
      <div className="p-6">
        <div className="text-gray-700">Checking sign-in…</div>
      </div>
    );
  }

  if (auth.error) {
    return (
      <div className="p-6">
        <div className="text-red-600">Auth error: {auth.error.message}</div>
        <button
          onClick={() => auth.signinRedirect()}
          className="mt-3 px-3 py-2 rounded bg-blue-600 text-white"
        >
          Try sign-in
        </button>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="p-6">
        <h2 className="text-xl font-semibold mb-2">Sign in required</h2>
        <p className="text-gray-700 mb-4">Redirecting to Cognito sign-in…</p>
      </div>
    );
  }

  return children;
}

const App = () => {
  const auth = useAuth();
  const eventsHookedRef = useRef(false);

  // Keep axios Bearer in sync with OIDC session
  useEffect(() => {
    window.__auth = auth; // dev helper

    if (auth?.isAuthenticated && auth?.user?.id_token) {
      setAuthToken(auth.user.id_token);
      try {
        localStorage.setItem("finops.id_token", auth.user.id_token);
      } catch {}
    } else {
      clearAuthToken();
      try {
        localStorage.removeItem("finops.id_token");
      } catch {}
    }

    // Register OIDC events once
    if (!eventsHookedRef.current && auth?.events) {
      eventsHookedRef.current = true;
      auth.events.addUserLoaded?.((u) => console.log("[OIDC] user loaded", u));
      auth.events.addUserUnloaded?.(() => console.log("[OIDC] user unloaded"));
      auth.events.addAccessTokenExpired?.(() =>
        console.warn("[OIDC] access token expired")
      );
      auth.events.addSilentRenewError?.((e) =>
        console.error("[OIDC] silent renew error", e)
      );
      auth.events.addUserSessionChanged?.(() =>
        console.log("[OIDC] session changed")
      );
    }
  }, [auth?.isAuthenticated, auth?.user?.id_token, auth]);

  // Hosted UI logout
  const signOutHostedUI = () => {
    const clientId = CLIENT_ID;
    if (!clientId) {
      alert("Missing VITE_CLIENT_ID in .env");
      return;
    }
    const logoutUrl = `${OIDC_DOMAIN}/logout?client_id=${encodeURIComponent(
      clientId
    )}&logout_uri=${encodeURIComponent(LOGOUT_REDIRECT)}`;
    auth.removeUser?.();
    clearAuthToken();
    window.location.href = logoutUrl;
  };

  // Dev helpers
  const idToken =
    auth?.user?.id_token || localStorage.getItem("finops.id_token") || "";
  const copyIdToken = async () => {
    try {
      await navigator.clipboard.writeText(idToken);
      alert("ID Token copied to clipboard!");
    } catch {
      alert("Failed to copy. See window.__auth?.user?.id_token");
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1">
        <Navbar />

        {/* Tiny auth toolbar */}
        <div className="px-6 pt-3">
          <div className="flex items-center gap-3 flex-wrap">
            {auth.isAuthenticated ? (
              <>
                <span className="text-sm text-gray-700">
                  Signed in as <b>{auth.user?.profile?.email || "user"}</b>
                </span>
                <button
                  onClick={() => {
                    auth.removeUser?.(); // local only
                    clearAuthToken();
                  }}
                  className="px-3 py-1.5 rounded bg-gray-200 hover:bg-gray-300 text-sm"
                  title="Clears local session only"
                >
                  Sign out (local)
                </button>
                <button
                  onClick={signOutHostedUI}
                  className="px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-900 text-white text-sm"
                  title="Hosted UI logout"
                >
                  Sign out (Hosted UI)
                </button>
                <button
                  onClick={copyIdToken}
                  className="px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-700 text-white text-sm"
                  title="Copy current ID Token to clipboard"
                >
                  Copy ID Token
                </button>
                <details className="text-xs text-gray-600">
                  <summary className="cursor-pointer">OIDC Debug</summary>
                  <div className="mt-1 max-w-full overflow-x-auto">
                    <div>
                      <b>token present:</b>{" "}
                      {idToken ? (
                        <span className="text-green-700">yes</span>
                      ) : (
                        <span className="text-red-700">no</span>
                      )}
                    </div>
                    <div className="mt-1">
                      <b>profile:</b>{" "}
                      <code className="whitespace-pre-wrap break-all">
                        {JSON.stringify(auth?.user?.profile || {}, null, 2)}
                      </code>
                    </div>
                  </div>
                </details>
              </>
            ) : (
              <button
                onClick={() => auth.signinRedirect()}
                className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm"
              >
                Sign in
              </button>
            )}
          </div>
        </div>

        <div className="p-6 overflow-y-auto flex-1 bg-gray-50">
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route
                path="/ai"
                element={
                  <RequireAuth>
                    <AIInsights />
                  </RequireAuth>
                }
              />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/clients" element={<Clients />} />
              <Route
                path="/actions"
                element={
                  <RequireAuth>
                    <Actions />
                  </RequireAuth>
                }
              />
              <Route
                path="/admin"
                element={
                  <RequireAuth>
                    <AdminBudgets />
                  </RequireAuth>
                }
              />
            </Routes>
          </ErrorBoundary>
        </div>
      </div>
    </div>
  );
};

export default App;
