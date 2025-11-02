// Profitability visualization + Budgets governance
// frontend/src/pages/Dashboard.jsx
import React, { useEffect, useMemo, useState } from "react";
import { useAuth } from "react-oidc-context";
import { toast } from "react-hot-toast";

// ✅ API namespace import (resilient to missing helpers)
import * as Api from "../utils/api";
import { BASE_URL } from "../utils/api";

// ✅ Bring the helper from a separate module so this file only exports a component
import { summarizeBudgetAlerts } from "../utils/budgets";

// keep explicit .jsx endings
import PieCostProfit from "../components/charts/PieCostProfit.jsx";
import MarginBar from "../components/charts/MarginBar.jsx";
import WasteBar from "../components/charts/WasteBar.jsx";
import RevenueDonut from "../components/charts/RevenueDonut.jsx";

// ------------------------- Local Storage helpers -------------------------
const LS_KEY = "finops.budgets";

function loadBudgetsFromLS() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveBudgetsToLS(obj) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(obj || {}));
  } catch {
    /* ignore */
  }
}

// ------------------------- Component -------------------------
export default function Dashboard() {
  const auth = useAuth();
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [data, setData] = useState(null);

  const [source, setSource] = useState("auto");
  const meta = useMemo(() => (data?.meta ? data.meta : {}), [data]);

  // Server alerts (array of {client, status, pct, budget})
  const alerts = useMemo(() => data?.alerts || [], [data]);
  const alertByClient = useMemo(() => {
    const m = {};
    (alerts || []).forEach((a) => (m[a.client] = a));
    return m;
  }, [alerts]);

  // --- Budgets state (client -> number) ---
  const [budgets, setBudgets] = useState({}); // { "ClientA": 5000, ... }
  const [syncingBudgets, setSyncingBudgets] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  // --------------------------------------------
  // Budgets bootstrap (local if guest, API if signed-in)
  // --------------------------------------------
  useEffect(() => {
    (async () => {
      if (auth?.isLoading) return;
      try {
        if (auth?.isAuthenticated && typeof Api.getBudgets === "function") {
          const server = await Api.getBudgets().catch(() => ({}));
          if (server && typeof server === "object") {
            setBudgets(server);
            saveBudgetsToLS(server);
            return;
          }
        }
        setBudgets(loadBudgetsFromLS());
      } catch {
        setBudgets(loadBudgetsFromLS());
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth?.isAuthenticated, auth?.isLoading]);

  // Ensure budgets has keys for displayed clients (don’t overwrite)
  useEffect(() => {
    const clients = data?.client_insights || [];
    if (!clients.length) return;
    setBudgets((prev) => {
      const next = { ...prev };
      let changed = false;
      for (const c of clients) {
        if (!(c.client in next)) {
          next[c.client] = ""; // empty until user sets
          changed = true;
        }
      }
      if (changed) saveBudgetsToLS(next);
      return changed ? next : prev;
    });
  }, [data]);

  const persistBudgets = async (nextObj) => {
    setBudgets(nextObj);
    saveBudgetsToLS(nextObj);

    // If not authenticated yet, keep it local (no 401 spam)
    if (!auth?.isAuthenticated || auth?.isLoading) {
      toast.success("Budgets saved locally (sign in to sync)");
      return;
    }

    if (typeof Api.saveBudgets === "function") {
      try {
        setSyncingBudgets(true);
        await Api.saveBudgets(nextObj);
        toast.success("Budgets synced");
      } catch (e) {
        toast.error(e?.message || "Failed to sync budgets, kept locally");
      } finally {
        setSyncingBudgets(false);
      }
    } else {
      toast.success("Budgets saved (local)");
    }
  };

  const setBudgetFor = (client, val) => {
    const n = val === "" ? "" : Math.max(0, Number(val) || 0);
    setBudgets((prev) => {
      const next = { ...prev, [client]: n };
      saveBudgetsToLS(next);
      return next;
    });
  };

  const saveBudgetFor = (client) => {
    const final = { ...budgets, [client]: budgets[client] || 0 };
    persistBudgets(final);
  };

  // --------------------- Load / Reload analysis ---------------------
  const reload = async () => {
    setLoading(true);
    setErr("");
    try {
      const effSource = source === "auto" ? null : source;
      const result = await Api.getAnalysis(effSource);
      setData(result);
    } catch (e) {
      setErr(e?.response?.data?.detail || e?.message || "Failed to load");
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const useLatestUpload = async () => {
    setLoading(true);
    setErr("");
    try {
      const key = await Api.fetchLatestKey();
      if (!key) {
        alert("No latest upload found for this user.");
        return;
      }
      const result = await Api.analyzeByKey(key);
      setData({ ...result, meta: { ...(result?.meta || {}), key, source: "history" } });
    } catch (e) {
      setErr(e?.response?.data?.detail || e?.message || "Failed to load latest upload");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source]);

  const clients = useMemo(() => data?.client_insights || [], [data]);

  // --------------------- Governance: server-driven alert chips + local fallback ---------------------
  const GovernanceLegend = () => (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span className="inline-flex items-center gap-2 px-2 py-1 rounded-full bg-amber-100 text-amber-900 border border-amber-200">
        <span className="w-2 h-2 rounded-full bg-amber-500" /> Warn (≥ 90% of budget)
      </span>
      <span className="inline-flex items-center gap-2 px-2 py-1 rounded-full bg-red-100 text-red-900 border border-red-200">
        <span className="w-2 h-2 rounded-full bg-red-600" /> Breach (≥ 100% of budget)
      </span>
      {syncingBudgets ? <span className="ml-2 text-gray-500">Syncing budgets…</span> : null}
    </div>
  );

  // If backend didn't send alerts for this client, compute a local fallback using budgets + cost.
  const computeLocalAlert = (clientName, actualSpend) => {
    const rawBudget = budgets?.[clientName];
    const budget = Number(rawBudget);
    if (!Number.isFinite(budget) || budget <= 0) return null;

    const pct = (Number(actualSpend || 0) / budget) * 100;
    if (pct >= 100) return { status: "breach", pct, budget };
    if (pct >= 90) return { status: "warn", pct, budget };
    return { status: "ok", pct, budget };
  };

  const alertBadge = (clientName, actualSpend) => {
    const a = alertByClient[clientName] || computeLocalAlert(clientName, actualSpend);
    if (!a) return null;

    if (a.status === "breach") {
      return (
        <span
          className="ml-2 text-[11px] px-2 py-0.5 rounded bg-red-100 text-red-800 border border-red-200"
          title={`Spend ${(a.pct || 0).toFixed(1)}% of $${Number(a.budget || 0).toLocaleString()}`}
        >
          Breach
        </span>
      );
    }
    if (a.status === "warn") {
      return (
        <span
          className="ml-2 text-[11px] px-2 py-0.5 rounded bg-amber-100 text-amber-900 border border-amber-200"
          title={`Spend ${(a.pct || 0).toFixed(1)}% of $${Number(a.budget || 0).toLocaleString()}`}
        >
          Warn
        </span>
      );
    }
    return (
      <span
        className="ml-2 text-[11px] px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200"
        title={`Spend ${(a.pct || 0).toFixed(1)}%`}
      >
        OK
      </span>
    );
  };

  // --------------------- PDF export (axios Blob via Api.exportPDF) ---------------------
  const downloadPdf = async () => {
    try {
      if (loading) return; // avoid exporting while loading data
      setDownloadingPdf(true);
      const params = {};
      if (meta?.source === "history" && meta?.key) {
        params.key = meta.key;
      } else if (source && source !== "auto") {
        params.source = source;
      }

      // ✅ Api.exportPDF returns { blob, filename }
      const { blob, filename } = await Api.exportPDF(params);

      const fname =
        filename ||
        `finops_report_${new Date().toISOString().replace(/[:.]/g, "")}.pdf`;

      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = fname;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);

      toast.success("Exported PDF");
    } catch (e) {
      console.error("Export PDF error:", e);
      toast.error(e?.message || "Failed to export PDF");
    } finally {
      setDownloadingPdf(false);
    }
  };

  // ------ Alert summary: server if present else local fallback ------
  const serverSummary = useMemo(() => {
    if (!alerts?.length) return null;
    const breach = alerts.filter((a) => a.status === "breach").length;
    const warn = alerts.filter((a) => a.status === "warn").length;
    const ok = alerts.filter((a) => a.status !== "breach" && a.status !== "warn").length;
    return { breach, warn, ok };
  }, [alerts]);

  const localSummary = useMemo(
    () => summarizeBudgetAlerts(clients, budgets),
    [clients, budgets]
  );

  const finalSummary = serverSummary || localSummary;
  const usingLocal = !serverSummary; // optional: to show a tiny hint

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Profitability Overview</h1>

      <OIDCDebugBar />

      {/* Governance legend */}
      <GovernanceLegend />

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm text-gray-600">
          Source:
          <select
            className="ml-2 border rounded px-2 py-1 text-sm"
            value={source}
            onChange={(e) => setSource(e.target.value)}
          >
            <option value="auto">Auto (backend decides)</option>
            <option value="s3">S3 default</option>
            <option value="local">Local sample</option>
          </select>
        </label>

        <button className="px-3 py-1.5 rounded bg-gray-800 text-white" onClick={reload} disabled={loading}>
          Reload
        </button>

        <button className="px-3 py-1.5 rounded bg-blue-600 text-white" onClick={useLatestUpload} disabled={loading}>
          Use latest upload
        </button>

        <button
          className="px-3 py-1.5 rounded bg-teal-600 text-white disabled:opacity-60"
          onClick={downloadPdf}
          disabled={downloadingPdf || loading}
          title="Download executive PDF with KPIs, client table & budget alerts"
        >
          {downloadingPdf ? "Generating PDF…" : "Download PDF"}
        </button>

        <button
          className="px-3 py-1.5 rounded bg-gray-100"
          onClick={() => {
            const cleared = {};
            const cs = data?.client_insights || [];
            cs.forEach((c) => (cleared[c.client] = ""));
            persistBudgets(cleared);
          }}
        >
          Reset budgets
        </button>
      </div>

      {/* Alerts summary panel (server-first, else local) */}
      {!loading && !err && data && (
        <div className="rounded-md border p-3 bg-white">
          <div className="text-sm font-medium mb-1">
            Budget Alerts {usingLocal ? <span className="text-[11px] text-gray-500">(local)</span> : null}
          </div>
          <div className="text-xs text-gray-600">
            <span className="inline-flex items-center gap-1 mr-3">
              <span className="w-2 h-2 rounded-full bg-red-600 inline-block" />
              <b>{finalSummary.breach}</b> Breach
            </span>
            <span className="inline-flex items-center gap-1 mr-3">
              <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" />
              <b>{finalSummary.warn}</b> Warn
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
              <b>{finalSummary.ok}</b> OK
            </span>
          </div>

          {!!(alerts || []).length && (
            <div className="mt-2 text-xs">
              <div className="font-medium mb-1">Top alerting clients</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-1">
                {(alerts || [])
                  .sort(
                    (a, b) =>
                      (b.status === "breach") - (a.status === "breach") || (b.pct || 0) - (a.pct || 0)
                  )
                  .slice(0, 5)
                  .map((a, i) => (
                    <div key={i} className="flex justify-between rounded border px-2 py-1">
                      <div>
                        {a.client}{" "}
                        <span className="text-gray-500">
                          ({(a.pct || 0).toFixed(1)}% of ${Number(a.budget || 0).toLocaleString()})
                        </span>
                      </div>
                      <div>
                        {a.status === "breach" ? (
                          <span className="text-red-700">BREACH</span>
                        ) : a.status === "warn" ? (
                          <span className="text-amber-700">WARN</span>
                        ) : (
                          <span className="text-emerald-700">OK</span>
                        )}
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}

      {loading && <div className="rounded border p-4 bg-gray-50">Loading…</div>}
      {!loading && err && (
        <div className="border border-red-200 bg-red-50 text-red-800 p-4 rounded">
          <div className="font-medium">Failed to load.</div>
          <div className="text-sm mt-1">{err}</div>
        </div>
      )}

      {!loading && !err && data && (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Stat label="Total Revenue" value={money(data.total_revenue)} />
            <Stat label="Total Cost" value={money(data.total_cost)} />
            <Stat label="Total Profit" value={money((data.total_revenue || 0) - (data.total_cost || 0))} />
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <PieCostProfit
                totalRevenue={Number(data.total_revenue || 0)}
                totalCost={Number(data.total_cost || 0)}
              />
              <RevenueDonut clientInsights={clients} topN={6} />
            </div>

            <MarginBar clientInsights={clients} topN={8} />

            <div className="lg:col-span-2">
              <WasteBar clientInsights={clients} topN={10} />
            </div>
          </div>

          {/* Client cards with Budget inputs + server/local alerts */}
          <div className="mt-6">
            <h2 className="text-lg font-semibold mb-2">Client Profitability & Budgets</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {clients.map((c, i) => {
                const current = budgets?.[c.client] ?? "";
                return (
                  <div key={i} className="rounded border p-4">
                    <div className="flex items-center justify-between">
                      <div className="font-medium">
                        {c.client}
                        {alertBadge(c.client, c.cost)}
                      </div>
                      <div className="flex items-center gap-2">
                        <label className="text-xs text-gray-500">Budget ($)</label>
                        <input
                          className="border rounded px-2 py-1 text-xs w-28"
                          value={current}
                          inputMode="numeric"
                          type="text"
                          placeholder="e.g. 5000"
                          onChange={(e) => setBudgetFor(c.client, e.target.value)}
                          onBlur={() => saveBudgetFor(c.client)}
                        />
                      </div>
                    </div>

                    <div className="text-sm text-gray-600 mt-2">
                      Revenue: {money(c.revenue)} <br />
                      Cost: {money(c.cost)} <br />
                      Margin: {money(c.margin)} <br />
                      License Waste: {pct(c.license_waste_pct)} | {c.health || "Unknown"}
                    </div>
                  </div>
                );
              })}
              {!clients.length && (
                <div className="text-sm text-gray-600">No client detail available for this dataset.</div>
              )}
            </div>
          </div>

          {/* Meta */}
          <div className="text-xs text-gray-500 mt-2">
            Source: <code>{meta?.source || "unknown"}</code>
            {meta?.key ? (
              <>
                {" "}
                | Key: <code>{meta.key}</code>
              </>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}

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
