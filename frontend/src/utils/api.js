// frontend/src/utils/api.js
// Centralized API client with OIDC token injection + helpers.

import axios from "axios";
import { getBrowserIdToken } from "./authDebug";

/** ---------- Base URL normalization ---------- */
function computeBase() {
  const raw = import.meta.env.VITE_API_BASE;
  // Default to "/api" if unset/empty/whitespace
  if (!raw || !String(raw).trim()) return "/api";
  let b = String(raw).trim();
  if (!/^https?:\/\//i.test(b) && !b.startsWith("/")) b = "/" + b;
  return b.replace(/\/+$/, "");
}

export const API_BASE = computeBase();
export const BASE_URL = API_BASE;

// ---------- axios instance + bearer ----------
const api = axios.create({ baseURL: API_BASE });

// Optional in-memory override (useful for tests)
let _bearer = "";
export function setAuthToken(token) {
  _bearer = token || "";
}
export function clearAuthToken() {
  _bearer = "";
}

// Attach token + sane defaults per request
api.interceptors.request.use((config) => {
  config.headers = config.headers || {};
  // Default headers
  config.headers.Accept = config.headers.Accept || "application/json";
  config.headers["Cache-Control"] = config.headers["Cache-Control"] || "no-store";
  config.headers.Pragma = config.headers.Pragma || "no-cache";
  config.headers["X-Requested-With"] = config.headers["X-Requested-With"] || "XMLHttpRequest";

  // Prefer explicit override, else pull fresh from localStorage (Cognito)
  const tok = _bearer || getBrowserIdToken();
  if (tok) {
    config.headers.Authorization = `Bearer ${tok}`;
  } else {
    delete config.headers.Authorization;
  }
  return config;
});

// Optionally react to 401/403 by clearing tokens (prevents bad loops)
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err?.response?.status;
    if (status === 401 || status === 403) {
      try {
        localStorage.removeItem("id_token");
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
      } catch {}
    }
    return Promise.reject(err);
  }
);

// ---------- analysis / recommendation ----------
export async function getAnalysis(source = null) {
  const params = {};
  if (typeof source === "string" && source) params.source = source;
  const { data } = await api.get("/analyze", { params });
  return data;
}

export async function analyzeByKey(key) {
  if (!key) throw new Error("key required");
  const { data } = await api.get("/analyze/by-key", { params: { key } });
  return data;
}

export async function recommendByKey(key) {
  if (!key) throw new Error("key required");
  const { data } = await api.get("/recommend/by-key", { params: { key } });
  const text = data?.text || data?.ai_recommendation || "";
  return {
    text,
    ai_recommendation: text,
    source: data?.source || "unknown",
    parsed_json: data?.parsed_json || null,
    raw: data,
  };
}

export async function getRecommendation() {
  const { data } = await api.get("/recommend");
  const text = data?.text || data?.ai_recommendation || "";
  return {
    text,
    ai_recommendation: text,
    source: data?.source || "unknown",
    parsed_json: data?.parsed_json || null,
    raw: data,
  };
}

// Kept for older imports
export async function recommend() {
  return getRecommendation();
}

// ---------- upload ----------
export async function uploadCSV(file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post("/upload", form);
  return data;
}

// ---------- history (server + local) ----------
const LS_HISTORY = "finops.history";
const LS_LASTKEY = "finops.lastKey";

function normalizeHistoryList(input) {
  if (!input) return [];
  if (Array.isArray(input)) {
    if (input.length === 0) return [];
    if (typeof input[0] === "string") return input.slice();
    if (typeof input[0] === "object" && input[0] !== null) {
      return input.map((o) => o.key).filter(Boolean);
    }
    return [];
  }
  if (input && Array.isArray(input.items)) {
    return input.items.map((o) => (typeof o === "string" ? o : o?.key)).filter(Boolean);
  }
  if (input && Array.isArray(input.files)) {
    if (typeof input.files[0] === "string") return input.files.slice();
    if (typeof input.files[0] === "object" && input.files[0] !== null) {
      return input.files.map((o) => o.key).filter(Boolean);
    }
  }
  return [];
}

export async function fetchHistory() {
  const { data } = await api.get("/history", { params: { _ts: Date.now() } });
  return normalizeHistoryList(data);
}

// Raw payload (if needed elsewhere)
export async function history() {
  const { data } = await api.get("/history", { params: { _ts: Date.now() } });
  return data;
}

export async function getRecentHistory(params = {}) {
  try {
    const { data } = await api.get("/history/recent", {
      params: { _ts: Date.now(), ...params },
    });

    const raw = Array.isArray(data) ? data : (data?.items || []);
    return raw.map((it) => {
      const msg =
        it?.message ??
        it?.title ??
        it?.text ??
        it?.event ??
        it?.detail ??
        "";
      const key =
        it?.key ??
        it?.dataset_key ??
        it?.upload_key ??
        it?.s3_key ??
        "";
      const ms = it?.time
        ? Date.parse(it.time)
        : (typeof it?.ts === "number" ? it.ts * 1000 : NaN);

      return {
        id: it?.id ?? it?.event_id ?? key,
        kind: it?.kind ?? "event",
        message: msg,
        key,
        ts: Number.isFinite(ms) ? Math.floor(ms / 1000) : undefined,
        time: Number.isFinite(ms) ? new Date(ms) : undefined,
        _raw: it,
      };
    });
  } catch (e) {
    if (e?.response?.status === 404) {
      const keys = await fetchHistory();
      return (keys || []).map((k) => ({
        id: k,
        kind: "upload",
        key: k,
        message: `Uploaded ${k}`,
      }));
    }
    console.warn("[history] failed:", e?.message);
    return [];
  }
}

export async function addHistory(event = {}) {
  const { data } = await api.post("/history/add", event); // bare body
  return data || { ok: true };
}

export async function fetchHistoryItems() {
  const { data } = await api.get("/history", { params: { _ts: Date.now() } });
  if (Array.isArray(data?.items)) {
    return data.items.map((o) => ({
      key: o.key,
      size: o.size,
      last_modified: o.last_modified,
    }));
  }
  const keys = normalizeHistoryList(data);
  return keys.map((k) => ({ key: k }));
}

export async function fetchLatestItem() {
  const { data } = await api.get("/history/latest", { params: { _ts: Date.now() } });
  return data?.item || null;
}

export async function fetchLatestKey() {
  const item = await fetchLatestItem();
  return item?.key || null;
}

export function addLocalHistory(key) {
  if (!key) return;
  try {
    const cur = JSON.parse(localStorage.getItem(LS_HISTORY) || "[]");
    if (!cur.includes(key)) {
      cur.unshift(key);
      localStorage.setItem(LS_HISTORY, JSON.stringify(cur.slice(0, 100)));
    }
    saveLastKey(key);
  } catch {
    // ignore
  }
}

export function getLocalHistory() {
  try {
    const cur = JSON.parse(localStorage.getItem(LS_HISTORY) || "[]");
    return Array.isArray(cur) ? cur : [];
  } catch {
    return [];
  }
}

export function mergeHistory(serverList = []) {
  const local = getLocalHistory();
  const set = new Set([...(serverList || []), ...local]);
  return Array.from(set);
}

export function saveLastKey(key) {
  if (!key) return;
  try {
    localStorage.setItem(LS_LASTKEY, key);
  } catch {}
}
export function readLastKey() {
  try {
    return localStorage.getItem(LS_LASTKEY) || "";
  } catch {
    return "";
  }
}

// ---------- clients (mock) ----------
export async function getClients() {
  try {
    const { data } = await api.get("/mockclients", { params: { _ts: Date.now() } });
    return Array.isArray(data) ? data : [];
  } catch (e) {
    console.warn("[clients] failed:", e?.message);
    return [];
  }
}

/** ---------- actions ---------- */
/** Ensure a title is present to satisfy backend schema */
function withTitle(action = {}) {
  if (action?.title && String(action.title).trim()) return action;

  const kind   = action?.type || "action";
  const who    = action?.client || action?.target || "all";
  const detail = action?.percent != null ? ` (${action.percent}%)` : "";
  return {
    title: `${kind} • ${who}${detail}`,
    ...action,
  };
}

export async function executeAction(action) {
  const envelope = {
    action: withTitle(action),
    // Keep demo-safe unless you explicitly want to execute
    preview_only: true,
  };

  try {
    const { data } = await api.post("/actions/execute", envelope);
    return data; // { executed, id, stored, preview, superops_result }
  } catch (e) {
    // Backward-compat: old route
    if (e?.response?.status === 404) {
      const { data } = await api.post("/execute_action", withTitle(action));
      return data;
    }
    throw e;
  }
}

// Backward-compat helpers
export const fetchAnalysis = getAnalysis;
export const getRecommendations = getRecommendation;

// default export if direct instance needed
export default api;

// ---------- Budgets ----------
export async function getBudgets(params = {}) {
  const { data } = await api.get("/budgets", { params });
  return data || {};
}

export async function saveBudgets(obj = {}, params = {}) {
  const { data } = await api.post("/budgets", obj, { params });
  return data || { ok: true };
}

// ---------- PDF Export ----------
export async function exportPDF(params = {}) {
  const res = await api.get("/export/pdf", {
    params,
    responseType: "arraybuffer",
    transformResponse: [(d) => d],
  });

  const contentType = (res.headers?.["content-type"] || "application/pdf").toLowerCase();
  const dispo = res.headers?.["content-disposition"] || "";
  let filename = "finops-report.pdf";
  const m = /filename\*=UTF-8''([^;]+)|filename="?([^"]+)"?/i.exec(dispo);
  if (m) filename = decodeURIComponent(m[1] || m[2] || filename);

  if (contentType.includes("json") || contentType.includes("text") || contentType.includes("xml")) {
    try {
      const txt = new TextDecoder("utf-8").decode(res.data);
      throw new Error(`Server error (not a PDF): ${txt.slice(0, 500)}`);
    } catch {
      throw new Error("Server did not return a valid PDF.");
    }
  }

  const bytes =
    res.data instanceof ArrayBuffer ? new Uint8Array(res.data) : new Uint8Array(res.data || []);
  const blob = new Blob([bytes], { type: contentType || "application/pdf" });

  return { blob, filename };
}

export async function getBenchmarks() {
  const { data } = await api.get("/benchmarks", { params: { _ts: Date.now() } });
  return data;
}
