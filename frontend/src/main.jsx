// frontend/src/main.jsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "react-oidc-context";
import { Toaster } from "react-hot-toast";
import App from "./App";
import "./index.css";

// ---- OIDC (Cognito) config ----
// Prefer explicit envs; fall back to window.origin in prod so we never hit localhost by mistake.
const REGION        = import.meta.env.VITE_COGNITO_REGION || "us-east-2";
const USER_POOL_ID  = import.meta.env.VITE_USER_POOL_ID;           // e.g. us-east-2_3hGBifjKi
const CLIENT_ID     = import.meta.env.VITE_CLIENT_ID;              // your app client id
const REDIRECT_URI  = import.meta.env.VITE_OIDC_REDIRECT_URI
  || (window?.location?.origin ? `${window.location.origin}/` : "http://localhost:5173/");
const LOGOUT_URI    = import.meta.env.VITE_OIDC_LOGOUT_REDIRECT_URI
  || (window?.location?.origin ? `${window.location.origin}/` : "http://localhost:5173/");

// Authority = Cognito OIDC issuer (recommended with react-oidc-context)
const AUTHORITY = `https://cognito-idp.${REGION}.amazonaws.com/${USER_POOL_ID}`;

// Optional: use hosted UI metadata instead of authority. Either works.
// const METADATA_URL = `${import.meta.env.VITE_OIDC_DOMAIN}/.well-known/openid-configuration`;

// Clean the URL after Cognito returns (?code=...&state=...)
function onSigninCallback() {
  if (window && window.history && window.location) {
    const url = new URL(window.location.href);
    url.searchParams.delete("code");
    url.searchParams.delete("state");
    window.history.replaceState({}, document.title, url.pathname + url.search + url.hash);
  }
}

const oidcConfig = {
  authority: AUTHORITY,
  // metadataUrl: METADATA_URL,  // <- use this instead of authority if you prefer the hosted domain
  client_id: CLIENT_ID,
  redirect_uri: REDIRECT_URI,
  post_logout_redirect_uri: LOGOUT_URI,
  response_type: "code",
  scope: "openid email profile",
  automaticSilentRenew: false,
  loadUserInfo: true,
  onSigninCallback,
};

// (Your logo/toaster code kept intact)
const LOGO_PATH = `${import.meta.env.BASE_URL || "/"}finops-logo.png`;
const FALLBACK_ICON = `${import.meta.env.BASE_URL || "/"}vite.svg`;

function LogoIcon(props) {
  return (
    <img
      src={LOGO_PATH}
      onError={(e) => (e.currentTarget.src = FALLBACK_ICON)}
      alt="FinOps+"
      style={{ width: 22, height: 22, borderRadius: "4px" }}
      {...props}
    />
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AuthProvider {...oidcConfig}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Toaster
          position="top-right"
          gutter={10}
          containerClassName="finops-toast-container"
          containerStyle={{ marginTop: 8, marginRight: 8 }}
          toastOptions={{
            className: "finops-toast",
            duration: 3500,
            style: {
              fontSize: "14px",
              borderRadius: "10px",
              padding: "10px 14px",
              fontWeight: 500,
              display: "flex",
              alignItems: "center",
              gap: "8px",
              boxShadow:
                "0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -2px rgba(0,0,0,0.06)",
              backdropFilter: "blur(6px)",
            },
            icon: <LogoIcon />,
            success: { style: { background: "#DCFCE7", color: "#065F46", border: "1px solid #86EFAC" } },
            error:   { style: { background: "#FEE2E2", color: "#991B1B", border: "1px solid #FCA5A5" } },
            loading: {
              icon: <LogoIcon style={{ width: 20, height: 20, borderRadius: "4px", animation: "spin 1.2s linear infinite" }} />,
              style: { background: "#FEF9C3", color: "#92400E", border: "1px solid #FACC15" },
            },
            blank:   { style: { background: "#EFF6FF", color: "#1E3A8A", border: "1px solid #93C5FD" } },
          }}
        />
        <App />
      </BrowserRouter>
    </AuthProvider>
  </React.StrictMode>
);
