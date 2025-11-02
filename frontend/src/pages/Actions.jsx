// frontend/src/pages/Actions.jsx
import React, { useEffect, useState } from "react";
import api, { executeAction, getRecentHistory } from "../utils/api";
import { toast } from "react-hot-toast";

function toMs(ts) {
  // accept seconds or ms
  const t = Number(ts || 0);
  return t < 2e10 ? t * 1000 : t;
}
function fmtMoney(n) {
  const v = Number(n || 0);
  if (!Number.isFinite(v)) return "—";
  return v.toLocaleString(undefined, { style: "currency", currency: "USD" });
}
function fmtTs(ts) {
  try {
    return new Date(toMs(ts)).toLocaleString();
  } catch {
    return "—";
  }
}

// Try to coerce a “recent history” event into an actions-row shape
function normalizeFromHistory(ev = {}) {
  // Expected recent event (from /history/recent):
  // { type: "action_executed", ts, key, title, action_id, stored, user_email, source?, action? }
  const a = ev.action || {};
  const title = a.title || ev.title || "—";
  return {
    ts: ev.ts || Date.now() / 1000,
    user_email: ev.user_email || "—",
    source: ev.source || "finops-agent",
    action: {
      title,
      targets: a.targets || [],
      est_impact_usd: a.est_impact_usd || 0,
    },
  };
}

// Try to normalize /actions (or /actions/log) response into a list of rows
function normalizeActionsPayload(data) {
  // target shape: [{ ts, user_email, source, action: { title, targets[], est_impact_usd } }, ...]
  if (!data) return [];

  // { items: [...] }
  if (Array.isArray(data.items)) {
    return data.items.map((row) => {
      const a = row?.action || {};
      return {
        ts: row.ts || Date.now() / 1000,
        user_email: row.user_email || "—",
        source: row.source || "finops-agent",
        action: {
          title: a.title || "—",
          targets: a.targets || [],
          est_impact_usd: a.est_impact_usd || 0,
        },
      };
    });
  }

  // [ ... ]
  if (Array.isArray(data)) {
    return data.map((row) => {
      const a = row?.action || {};
      return {
        ts: row.ts || Date.now() / 1000,
        user_email: row.user_email || "—",
        source: row.source || "finops-agent",
        action: {
          title: a.title || "—",
          targets: a.targets || [],
          est_impact_usd: a.est_impact_usd || 0,
        },
      };
    });
  }

  // Fallback: nothing recognized
  return [];
}

export default function Actions() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      // 1) Primary: /actions
      try {
        const { data } = await api.get("/actions", { params: { _ts: Date.now() } });
        const rows = normalizeActionsPayload(data);
        if (rows.length > 0 || Array.isArray(data?.items) || Array.isArray(data)) {
          setItems(rows.sort((a, b) => toMs(b.ts) - toMs(a.ts)));
          return;
        }
      } catch (e1) {
        // If 404, try /actions/log
        if (e1?.response?.status !== 404) throw e1;
      }

      // 2) Fallback: /actions/log
      try {
        const { data } = await api.get("/actions/log", { params: { _ts: Date.now() } });
        const rows = normalizeActionsPayload(data);
        if (rows.length > 0) {
          setItems(rows.sort((a, b) => toMs(b.ts) - toMs(a.ts)));
          return;
        }
      } catch (e2) {
        // ignore; we will try recent history
      }

      // 3) Last resort: /history/recent?type=action_executed
      try {
        const recents = await getRecentHistory({ type: "action_executed", limit: 200 });
        const rows = (recents || []).map(normalizeFromHistory);
        setItems(rows.sort((a, b) => toMs(b.ts) - toMs(a.ts)));
        return;
      } catch (e3) {
        // If even this fails, show error below
        throw e3;
      }
    } catch (e) {
      console.error("[Actions] load failed:", e);
      toast.error(e?.message || "Failed to load actions");
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // Optional: auto-refresh every 30s during demo
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  const rerun = async (evt) => {
    const action = evt?.action || {};
    try {
      const res = await executeAction(action);
      toast.success(`Re-queued: ${action?.title || "action"}`);
      load();
      return res;
    } catch (e) {
      toast.error("Failed to re-run");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Actions Log</h1>
        <button className="px-3 py-1.5 rounded bg-gray-800 text-white" onClick={load} disabled={loading}>
          Refresh
        </button>
      </div>

      <div className="rounded border bg-white">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr className="text-left">
              <th className="px-3 py-2">Time</th>
              <th className="px-3 py-2">User</th>
              <th className="px-3 py-2">Title</th>
              <th className="px-3 py-2">Targets</th>
              <th className="px-3 py-2">Est. Impact</th>
              <th className="px-3 py-2">Source</th>
              <th className="px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && !loading && (
              <tr>
                <td className="px-3 py-4 text-gray-500" colSpan={7}>
                  No actions captured yet.
                </td>
              </tr>
            )}
            {items.map((evt, i) => {
              const a = evt?.action || {};
              return (
                <tr key={i} className="border-t">
                  <td className="px-3 py-2">{fmtTs(evt.ts)}</td>
                  <td className="px-3 py-2">{evt.user_email || "—"}</td>
                  <td className="px-3 py-2 font-medium">{a.title || "—"}</td>
                  <td className="px-3 py-2">{(a.targets || []).join(", ") || "—"}</td>
                  <td className="px-3 py-2">{fmtMoney(a.est_impact_usd)}</td>
                  <td className="px-3 py-2 text-xs text-gray-500">{evt.source || "finops-agent"}</td>
                  <td className="px-3 py-2">
                    <button
                      className="px-2 py-1 rounded bg-amber-600 text-white"
                      onClick={() => rerun(evt)}
                    >
                      Re-run
                    </button>
                  </td>
                </tr>
              );
            })}
            {loading && (
              <tr>
                <td className="px-3 py-4 text-gray-500" colSpan={7}>
                  Loading…
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
