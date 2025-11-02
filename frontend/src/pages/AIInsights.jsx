// frontend/src/pages/AIInsights.jsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "react-oidc-context";
import {
  analyzeByKey,
  getAnalysis,
  fetchHistory,
  mergeHistory,
  readLastKey,
  saveLastKey,
  getRecommendation,
  recommendByKey,
  // removed getRecentHistory
  addHistory, // keep: still persist events server-side
} from "../utils/api";

import AIActionList from "../components/AIActionList";
import PriorityLegend from "../components/PriorityLegend";
import ToastActivityFeed from "../components/ToastActivityFeed";
import { toast } from "react-hot-toast";

/**
 * AI Insights page (Recent Activity card removed)
 * - Keeps ToastActivityFeed (visual toasts)
 * - Still persists action events to /api/history/add (no on-screen list)
 * - Benchmark panel on header
 */
export default function AIInsights() {
  const auth = useAuth();

  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [data, setData] = useState(null);

  const [recLoading, setRecLoading] = useState(false);
  const [recErr, setRecErr] = useState("");
  const [rec, setRec] = useState(null);

  const [history, setHistory] = useState([]);
  const [selectedKey, setSelectedKey] = useState("");

  const [currentKey, setCurrentKey] = useState("");
  const [currentSource, setCurrentSource] = useState("");

  const [recKey, setRecKey] = useState("");
  const reqIdRef = useRef(0);

  // Benchmarks (API with local fallback)
  const [bench, setBench] = useState(null);
  const [benchErr, setBenchErr] = useState("");

  const meta = useMemo(() => (data?.meta ? data.meta : {}), [data]);

  const refreshHistory = async () => {
    try {
      const server = await fetchHistory();
      const merged = mergeHistory(server);
      setHistory(merged);
      return merged;
    } catch (e) {
      console.warn("[history] failed", e?.message);
      const merged = mergeHistory([]);
      setHistory(merged);
      return merged;
    }
  };

  const loadSnapshot = async ({ key } = {}) => {
    const myId = ++reqIdRef.current;
    setErr("");
    setLoading(true);
    try {
      if (key) {
        const result = await analyzeByKey(key);
        if (myId !== reqIdRef.current) return;

        setData({ ...result, meta: { ...(result?.meta || {}), key, source: "history" } });
        setCurrentKey(key);
        setCurrentSource("history");

        setRec(null);
        setRecErr("");
        saveLastKey(key);
        toast.success("Snapshot loaded from history");
      } else {
        const result = await getAnalysis("auto");
        if (myId !== reqIdRef.current) return;

        setData({ ...result, meta: { ...(result?.meta || {}), source: result?.meta?.source || "auto" } });
        setCurrentKey("");
        setCurrentSource(result?.meta?.source || "auto");

        setRec(null);
        setRecErr("");
        toast.success("Auto dataset loaded");
      }
    } catch (ex) {
      if (myId !== reqIdRef.current) return;
      const msg = ex?.response?.data?.detail || ex?.message || "Failed to load insights";
      setErr(String(msg));
      setData(null);
      setCurrentKey("");
      setCurrentSource("");
      toast.error(`Load failed: ${msg}`);
    } finally {
      if (myId === reqIdRef.current) setLoading(false);
    }
  };

  const loadRecommendations = async () => {
    setRecErr("");
    setRec(null);
    setRecLoading(true);
    try {
      if (currentKey) {
        const r = await recommendByKey(currentKey);
        setRec(r);
        setRecKey(currentKey);
      } else {
        const r = await getRecommendation();
        setRec(r);
        setRecKey("");
      }
      toast.success("Insights generated");
    } catch (ex) {
      const msg = ex?.response?.data?.detail || ex?.message || "Failed to get recommendations";
      setRecErr(String(msg));
      toast.error(`AI error: ${msg}`);
    } finally {
      setRecLoading(false);
    }
  };

  // ---- Local fallback benchmark from the current dataset (weighted avg by cost) ----
  const localBenchmark = useMemo(() => {
    if (!data?.client_insights?.length) return null;
    let totalCost = 0;
    let weighted = 0;
    for (const c of data.client_insights) {
      const cost = Number(c.cost || 0);
      const waste = Number(c.license_waste_pct || 0);
      if (cost > 0) {
        totalCost += cost;
        weighted += cost * waste;
      }
    }
    if (totalCost <= 0) return null;
    return {
      source: "local",
      industry: "MSP",
      industry_waste_pct: Math.max(0, Math.min(100, weighted / totalCost)),
      notes: "Local fallback computed from current dataset.",
    };
  }, [data]);

  // ---- Try API benchmark; tolerate multiple JSON shapes; fallback to local ----
  const loadBenchmark = async () => {
    setBenchErr("");
    setBench(null);
    try {
      const base = import.meta.env.VITE_API_BASE || "";
      const url = `${base}/benchmarks?industry=msp`;
      const res = await fetch(url, { headers: { Accept: "application/json" } });

      const ct = (res.headers.get("content-type") || "").toLowerCase();
      if (!res.ok || !ct.includes("application/json")) {
        throw new Error("Benchmark API not available (non-JSON).");
      }

      const j = await res.json();

      const pickNumber = (v) => {
        if (typeof v === "number" && Number.isFinite(v)) return v;
        if (typeof v === "string") {
          const n = parseFloat(v);
          if (Number.isFinite(n)) return n;
        }
        return undefined;
      };

      let pctVal =
        pickNumber(j?.industry_waste_pct) ??
        pickNumber(j?.industry_avg_waste_pct) ??
        pickNumber(j?.waste_pct) ??
        pickNumber(j?.avg_waste_pct) ??
        pickNumber(j?.industryWastePct) ??
        (typeof j === "number" ? j : undefined);

      if (pctVal === undefined) throw new Error("Benchmark payload missing industry_waste_pct");
      pctVal = Math.max(0, Math.min(100, pctVal));

      setBench({
        source: j?.source || "api",
        industry: j?.industry || "MSP",
        industry_waste_pct: pctVal,
        notes: j?.notes || "",
        raw: j,
      });
    } catch (e) {
      console.warn("[benchmark] falling back:", e?.message);
      if (localBenchmark) {
        setBench(localBenchmark);
      } else {
        setBenchErr(e?.message || "Benchmark unavailable");
      }
    }
  };

  // initial load
  useEffect(() => {
    (async () => {
      const merged = await refreshHistory();
      const last = readLastKey();
      if (last && merged.includes(last)) {
        setSelectedKey(last);
        await loadSnapshot({ key: last });
      } else if (merged.length) {
        setSelectedKey(merged[0]);
        await loadSnapshot({ key: merged[0] });
      } else {
        await loadSnapshot(); // auto dataset
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // refresh benchmark when dataset changes (so local fallback is meaningful)
  useEffect(() => {
    loadBenchmark();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.meta?.key, data?.total_cost]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">AI Insights</h1>
          <OIDCDebugBar />
        </div>

        {/* Benchmark panel (robust to missing API) */}
        <div
          className={`rounded-md px-3 py-2 text-sm ${
            benchErr
              ? "bg-red-50 text-red-700 border border-red-200"
              : "bg-gray-50 text-gray-800 border border-gray-200"
          }`}
          title={
            benchErr
              ? benchErr
              : bench
              ? `Source: ${bench.source} | Industry: ${bench.industry}${bench.notes ? " • " + bench.notes : ""}`
              : ""
          }
        >
          <div className="font-medium">Benchmark</div>
          {benchErr ? (
            <div>{benchErr}</div>
          ) : bench ? (
            <div>
              Industry waste avg: <b>{pct(bench.industry_waste_pct)}</b>{" "}
              <span className="text-xs text-gray-500">({bench.source})</span>
            </div>
          ) : (
            <div className="text-gray-500">Loading…</div>
          )}
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3">
        <select
          className="border rounded px-2 py-1 text-sm"
          value={selectedKey}
          onChange={(e) => setSelectedKey(e.target.value)}
        >
          {history.length === 0 ? <option value="">— Select historical upload —</option> : null}
          {history.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>

        <button
          className="px-3 py-1.5 rounded bg-black text-white disabled:opacity-60"
          onClick={() => selectedKey && loadSnapshot({ key: selectedKey })}
          disabled={!selectedKey || loading}
        >
          Load from selected
        </button>

        <button
          className="px-3 py-1.5 rounded bg-blue-600 text-white disabled:opacity-60"
          onClick={loadRecommendations}
          disabled={recLoading}
        >
          Generate Insights
        </button>

        <button
          className="px-3 py-1.5 rounded bg-gray-200"
          onClick={refreshHistory}
          title="Refresh history"
        >
          Refresh history
        </button>
      </div>

      {/* Main + Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* MAIN CONTENT (2/3) */}
        <div className="lg:col-span-2 space-y-4">
          {/* What is on screen + what recs used */}
          <div className="text-xs text-gray-600">
            <div>
              Viewing: <code>{currentSource || "-"}</code>
              {currentKey ? (
                <>
                  {" "}
                  key: <code>{currentKey}</code>
                </>
              ) : null}
            </div>
            <div>
              Last recommendations were based on:{" "}
              {recKey ? <code>{recKey}</code> : <code>auto (default dataset)</code>}
            </div>
          </div>

          {loading && <div className="rounded border p-4 bg-gray-50">Loading snapshot…</div>}

          {!loading && err && (
            <div className="border border-red-200 bg-red-50 text-red-800 p-4 rounded">
              <div className="font-medium">Failed to load snapshot.</div>
              <div className="text-sm mt-1">{err}</div>
            </div>
          )}

          {!loading && !err && data && (
            <>
              {/* KPI Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Stat label="Total Revenue" value={money(data.total_revenue)} />
                <Stat label="Total Cost" value={money(data.total_cost)} />
                <Stat label="Total Profit" value={money(data.total_profit)} />
              </div>

              {/* Client Table */}
              <div className="rounded border p-0 overflow-hidden">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left border-b bg-gray-50">
                      <th className="py-2 pl-4 pr-2">Client</th>
                      <th className="py-2 pr-4">Revenue</th>
                      <th className="py-2 pr-4">Cost</th>
                      <th className="py-2 pr-4">Margin</th>
                      <th className="py-2 pr-4">Waste %</th>
                      <th className="py-2 pr-4">Health</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.client_insights || []).map((c, i) => (
                      <tr key={`${c.client}-${i}`} className="border-b last:border-none">
                        <td className="py-2 pl-4 pr-2">{c.client}</td>
                        <td className="py-2 pr-4">{money(c.revenue)}</td>
                        <td className="py-2 pr-4">{money(c.cost)}</td>
                        <td className="py-2 pr-4">{money(c.margin)}</td>
                        <td className="py-2 pr-4">{pct(c.license_waste_pct)}</td>
                        <td className="py-2 pr-4">{c.health || "Unknown"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="text-xs text-gray-500">
                From: <code>{meta?.key || "—"}</code>{" "}
                <span className="ml-3">
                  Source: <code>{meta?.source || "unknown"}</code>
                </span>
              </div>

              {/* Recommendations (raw text) */}
              <div className="rounded border p-4 mt-2">
                <div className="my-3">
                  <PriorityLegend />
                </div>
                <h2 className="font-semibold mb-2">AI Recommendations</h2>
                {recLoading && <div className="text-sm text-gray-600">Generating…</div>}
                {!recLoading && recErr && <div className="text-sm text-red-700">{recErr}</div>}
                {!recLoading && !recErr && rec && (
                  <div className="text-sm whitespace-pre-wrap">
                    {rec.ai_recommendation || rec.text || ""}
                  </div>
                )}
                {!recLoading && !recErr && !rec && (
                  <div className="text-sm text-gray-600">
                    Click “Generate Insights” after loading a dataset.
                  </div>
                )}
                <div className="text-xs text-gray-500 mt-2">
                  Model: <code>{rec?.source || "unknown"}</code>
                  {"  "} | Context: {recKey ? <code>{recKey}</code> : <code>auto</code>}
                </div>
              </div>

              {/* AI Insights — Details */}
              {rec?.parsed_json?.actions?.length ? (
                <div className="rounded border p-4 space-y-3">
                  <h2 className="font-semibold">AI Insights — Details</h2>
                  <div className="grid md:grid-cols-2 gap-3">
                    {rec.parsed_json.actions.map((a, idx) => (
                      <div key={`${a.title}-${idx}`} className="rounded-lg border p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="font-medium">{a.title}</div>
                          <RiskBadge risk={a.risk} />
                        </div>
                        <div className="text-sm text-gray-700 mt-1">{a.reason}</div>

                        <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                          <Info
                            label="Potential savings"
                            value={`${money(a.est_impact_usd)}${
                              a?.savings_pct
                                ? `  (${a.savings_pct.toFixed ? a.savings_pct.toFixed(1) : a.savings_pct}% )`
                                : ""
                            }`}
                          />
                          <Info label="Confidence" value={confPct(a.confidence)} />
                          <Info label="Current cost" value={money(a.current_cost)} />
                          <Info label="Projected cost" value={money(a.projected_cost)} />
                        </div>

                        {a?.targets?.length ? (
                          <div className="text-xs text-gray-500 mt-2">
                            Targets: {a.targets.join(", ")}
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {/* AI Actions (execute + persist event; no Recent Activity card) */}
              {rec?.parsed_json?.actions?.length ? (
                <div className="rounded border p-4">
                  <h2 className="font-semibold mb-3">AI Actions</h2>
                  <AIActionList
                    actions={rec.parsed_json.actions}
                    currentKey={recKey || currentKey || ""}
                    onExecuted={async (summary) => {
                      try {
                        const event = {
                          type: "action_executed",
                          ts: Math.floor(Date.now() / 1000),
                          key: summary.key || recKey || currentKey || "",
                          title: summary.title,
                          action_id: summary.id || "",
                          stored: !!summary.stored,
                          user_email: auth?.user?.profile?.email || "guest",
                        };
                        await addHistory(event); // persist only
                      } catch (e) {
                        console.warn("history add failed:", e?.message);
                      }
                      toast.success(`Saved: ${summary.title} (id: ${summary.id || "n/a"})`, {
                        duration: 4000,
                      });
                    }}
                  />
                </div>
              ) : null}
            </>
          )}
        </div>

        {/* SIDEBAR (1/3) — keep only visual toasts */}
        <div className="space-y-4">
          <ToastActivityFeed limit={5} />
        </div>
      </div>
    </div>
  );
}

/* ----------------------- Helpers & Debug ----------------------- */

function OIDCDebugBar() {
  const auth = useAuth();
  const email = auth?.user?.profile?.email || "guest";
  const copyId = async () => {
    const tok = auth?.user?.id_token || "";
    if (!tok) return alert("No ID token found in OIDC session.");
    await navigator.clipboard.writeText(tok);
    alert("ID token copied to clipboard.");
  };
  return (
    <div className="text-sm text-gray-700 flex items-center gap-2">
      Signed in as <b>{email}</b>
      <button onClick={copyId} className="px-3 py-1 rounded bg-violet-600 text-white">
        Copy ID Token
      </button>
      <span className="text-gray-400">▸ OIDC Debug</span>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-lg border p-4">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-xl font-semibold">{value}</div>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div className="rounded border p-3">
      <div className="text-[11px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className="text-sm font-medium">{value || "—"}</div>
    </div>
  );
}

function RiskBadge({ risk }) {
  const tone =
    risk === "high"
      ? "bg-red-100 text-red-700 border-red-200"
      : risk === "medium"
      ? "bg-amber-100 text-amber-700 border-amber-200"
      : "bg-emerald-100 text-emerald-700 border-emerald-200";
  const txt = risk ? risk.toString().toUpperCase() : "LOW";
  return <span className={`text-xs px-2 py-1 rounded border ${tone}`}>{txt}</span>;
}

function money(n) {
  if (n === null || n === undefined) return "—";
  const v = Number(n);
  if (Number.isNaN(v)) return "—";
  return v.toLocaleString(undefined, { style: "currency", currency: "USD" });
}
function pct(n) {
  if (n === null || n === undefined) return "—";
  const v = Number(n);
  if (Number.isNaN(v)) return "—";
  return `${v.toFixed(1)}%`;
}
function confPct(n) {
  if (n === null || n === undefined) return "—";
  const v = Number(n);
  if (Number.isNaN(v)) return "—";
  const p = Math.max(0, Math.min(1, v)) * 100;
  return `${p.toFixed(0)}%`;
}
