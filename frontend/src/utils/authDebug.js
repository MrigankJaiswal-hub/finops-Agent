// src/utils/authDebug.js
// Lightweight Cognito Auth (Code + PKCE) with origin-aware redirects.
// ENV needed: VITE_COGNITO_DOMAIN, VITE_COGNITO_CLIENT_ID

const COGNITO_DOMAIN = import.meta.env.VITE_COGNITO_DOMAIN;    // e.g. https://your-domain.auth.us-east-2.amazoncognito.com
const CLIENT_ID      = import.meta.env.VITE_COGNITO_CLIENT_ID; // e.g. 5sop8nmqobu3fflaqres1ckvgq

if (!COGNITO_DOMAIN || !CLIENT_ID) {
  console.warn("Cognito env vars missing: VITE_COGNITO_DOMAIN / VITE_COGNITO_CLIENT_ID");
}

// Compute redirects from current origin (works for localhost & CloudFront)
const ORIGIN = window.location.origin.replace(/\/$/, "");
const REDIRECT_URI = `${ORIGIN}/`;
const LOGOUT_URI   = `${ORIGIN}/`;
const SCOPES       = ["openid"]; // add "email","profile" if you enabled them

// --------------------- PKCE helpers ---------------------
async function sha256Base64Url(input) {
  const enc = new TextEncoder().encode(input);
  const hash = await crypto.subtle.digest("SHA-256", enc);
  // base64url
  return btoa(String.fromCharCode(...new Uint8Array(hash)))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function randomString(len = 64) {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~";
  const arr = crypto.getRandomValues(new Uint8Array(len));
  let out = "";
  for (let i = 0; i < len; i++) out += chars[arr[i] % chars.length];
  return out;
}

// --------------------- Token storage ---------------------
export function getStoredIdToken() {
  return localStorage.getItem("id_token") || null;
}
export function getStoredAccessToken() {
  return localStorage.getItem("access_token") || null;
}
export function clearTokens() {
  ["id_token", "access_token", "refresh_token", "code_verifier"].forEach(k => localStorage.removeItem(k));
}

// Backward-compatible helpers (keeps your old API shape)
export function getBrowserAccessToken() {
  // Prefer new storage
  const t = getStoredAccessToken();
  if (t) return t;
  // Fallback to old oidc.user blob if present
  const k = Object.keys(localStorage).find(x => x.startsWith("oidc.user"));
  if (!k) return null;
  try { return JSON.parse(localStorage.getItem(k))?.access_token || null; } catch { return null; }
}

export function getBrowserIdToken() {
  // Prefer new storage
  const t = getStoredIdToken();
  if (t) return t;
  // Fallback to old oidc.user blob if present
  const k = Object.keys(localStorage).find(x => x.startsWith("oidc.user"));
  if (!k) return null;
  try { return JSON.parse(localStorage.getItem(k))?.id_token || null; } catch { return null; }
}

// --------------------- Public auth API ---------------------
export async function beginLogin() {
  const verifier = randomString(64);
  const challenge = await sha256Base64Url(verifier);
  localStorage.setItem("code_verifier", verifier);

  const p = new URLSearchParams({
    client_id: CLIENT_ID,
    response_type: "code",
    scope: SCOPES.join(" "),
    redirect_uri: REDIRECT_URI,
    code_challenge_method: "S256",
    code_challenge: challenge
  });

  window.location.assign(`${COGNITO_DOMAIN}/oauth2/authorize?${p.toString()}`);
}

export function logout() {
  clearTokens();
  const p = new URLSearchParams({
    client_id: CLIENT_ID,
    logout_uri: LOGOUT_URI
  });
  window.location.assign(`${COGNITO_DOMAIN}/logout?${p.toString()}`);
}

/**
 * Call once on app load. If the URL contains ?code=..., exchanges it for tokens,
 * stores them, and removes query params from the URL.
 *
 * Usage (e.g., in src/main.jsx or App.jsx):
 *   import { completeLoginIfNeeded } from "./utils/authDebug";
 *   completeLoginIfNeeded();
 */
export async function completeLoginIfNeeded() {
  const url = new URL(window.location.href);
  const code = url.searchParams.get("code");
  if (!code) return false;

  const verifier = localStorage.getItem("code_verifier");
  if (!verifier) {
    console.warn("PKCE verifier missing; cannot complete login.");
    return false;
  }

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: CLIENT_ID,
    code,
    redirect_uri: REDIRECT_URI,
    code_verifier: verifier
  });

  const tokenUrl = `${COGNITO_DOMAIN}/oauth2/token`;
  const res = await fetch(tokenUrl, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body
  });

  if (!res.ok) {
    console.error("Token exchange failed:", await res.text());
    return false;
  }

  const json = await res.json();
  if (json.id_token)     localStorage.setItem("id_token", json.id_token);
  if (json.access_token) localStorage.setItem("access_token", json.access_token);
  if (json.refresh_token)localStorage.setItem("refresh_token", json.refresh_token);

  // remove ?code&state from address bar
  url.searchParams.delete("code");
  url.searchParams.delete("state");
  history.replaceState({}, document.title, url.toString());
  return true;
}
