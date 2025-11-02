// frontend/src/components/AIActionList.jsx
import React, { useState } from "react";
import { executeAction } from "../utils/api";
import { toast } from "react-hot-toast";

/**
 * AIActionList
 * Props:
 * - actions: [{ title, reason, est_impact_usd|estImpact, targets[], action_type?, key?, confidence?, savings_pct?, current_cost?, projected_cost? }, ...]
 * - currentKey: string (S3 key / dataset identifier to bind actions to)
 * - onExecuted?: (summary) => void  // optional callback after successful execution
 */
export default function AIActionList({ actions = [], currentKey = "", onExecuted }) {
  const [busy, setBusy] = useState(null);
  const [executedMap, setExecutedMap] = useState({}); // idx → {id, ts}
  const [log, setLog] = useState([]);

  if (!actions || actions.length === 0) {
    return <div style={{ color: "#666" }}>No structured actions returned by AI.</div>;
  }

  const money = (n) => {
    const v = Number(n);
    if (!Number.isFinite(v)) return "—";
    return v.toLocaleString(undefined, { style: "currency", currency: "USD" });
  };

  // normalize: allow estImpact or est_impact_usd
  const getImpact = (a) => {
    if (a == null) return undefined;
    if (a.est_impact_usd != null) return a.est_impact_usd;
    if (a.estImpact != null) return a.estImpact;
    return undefined;
  };

  const onAuto = async (a, idx) => {
    try {
      setBusy(idx);

      // build normalized payload
      const payload = {
        ...a,
        action_type: a.action_type || "optimize_license",
        key: currentKey || a.key || null,
        est_impact_usd: getImpact(a),
      };

      // call API (api.js already posts { action: payload } and falls back if needed)
      const p = executeAction(payload);
      toast.promise(p, {
        loading: "Executing action…",
        success: "Action executed",
        error: "Execution failed",
      });

      const res = await p;

      // prefer res.id; fallback to legacy res.actionId
      const actionId = res?.id ?? res?.actionId ?? "—";

      const summary = {
        ts: Date.now(),
        id: actionId,
        stored: res?.stored,
        title: payload.title,
        key: payload.key,
        result: res,
      };

      setLog((prev) => [
        { ts: summary.ts, id: summary.id, text: `Executed: ${payload.title} → store=${res?.stored}` },
        ...prev,
      ]);

      // Mark as executed (gray out)
      setExecutedMap((prev) => ({
        ...prev,
        [idx]: { id: summary.id || "—", ts: summary.ts },
      }));

      toast.success(
        `Executed: ${payload.title}\nSaved: ${res?.stored ? "yes" : "no"}${summary.key ? `\nKey: ${summary.key}` : ""}`,
        { duration: 4000 }
      );

      if (typeof onExecuted === "function") onExecuted(summary);
    } catch (e) {
      const msg =
        e?.response?.data?.detail ||
        e?.response?.data?.message ||
        e?.message ||
        (typeof e === "object" ? JSON.stringify(e) : String(e));
      toast.error(`Execute failed: ${msg}`);
      console.error("[AIActionList] execute failed:", e);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div style={{ marginTop: 8 }}>
      {actions.map((a, idx) => {
        const executed = executedMap[idx];
        const impact = getImpact(a);
        return (
          <div
            key={idx}
            style={{
              border: "1px solid #eee",
              borderRadius: 10,
              padding: 12,
              marginBottom: 8,
              background: "#fff",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <div style={{ fontWeight: 600 }}>{a.title}</div>
              {/* Optional risk/confidence chips if present */}
              {a?.risk ? (
                <span
                  style={{
                    fontSize: 12,
                    padding: "2px 8px",
                    borderRadius: 12,
                    border: "1px solid #ddd",
                    background:
                      a.risk === "high" ? "#fee2e2" : a.risk === "medium" ? "#fef3c7" : "#dcfce7",
                    color:
                      a.risk === "high" ? "#991b1b" : a.risk === "medium" ? "#92400e" : "#065f46",
                  }}
                >
                  {String(a.risk).toUpperCase()}
                </span>
              ) : null}
            </div>

            <div style={{ fontSize: 13, color: "#555", marginTop: 4 }}>{a.reason}</div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 8, fontSize: 13 }}>
              <div>
                <b>Est. Impact</b>: {impact != null ? money(impact) : "—"}
                {a?.savings_pct != null ? (
                  <span style={{ color: "#666" }}> ({Number(a.savings_pct).toFixed?.(1) ?? a.savings_pct}%)</span>
                ) : null}
              </div>
              <div>
                <b>Targets</b>: {(a.targets || []).join(", ") || "—"}
              </div>
              {a?.current_cost != null ? (
                <div>
                  <b>Current cost</b>: {money(a.current_cost)}
                </div>
              ) : null}
              {a?.projected_cost != null ? (
                <div>
                  <b>Projected cost</b>: {money(a.projected_cost)}
                </div>
              ) : null}
            </div>

            <div style={{ marginTop: 10 }}>
              <button
                disabled={busy === idx || !!executed}
                onClick={() => onAuto(a, idx)}
                style={{
                  padding: "6px 10px",
                  borderRadius: 6,
                  background: executed
                    ? "#9CA3AF"
                    : busy === idx
                    ? "#6B7280"
                    : "#111827",
                  color: "#fff",
                  cursor: busy === idx || executed ? "not-allowed" : "pointer",
                }}
                title={currentKey ? `Execute for ${currentKey}` : "Execute (auto context)"}
              >
                {executed ? "✅ Executed" : busy === idx ? "Executing..." : "⚡ Auto-execute"}
              </button>

              {executed && (
                <div style={{ fontSize: 12, color: "#555", marginTop: 4 }}>
                  Action ID: <code>{executed.id}</code>{" "}
                  <span style={{ color: "#999" }}>
                    ({new Date(executed.ts).toLocaleTimeString()})
                  </span>
                </div>
              )}
            </div>
          </div>
        );
      })}

      {log.length > 0 && (
        <div style={{ marginTop: 12, fontSize: 12, color: "#666" }}>
          <b>Recent actions:</b>
          <ul style={{ marginTop: 6 }}>
            {log.slice(0, 5).map((l, i) => (
              <li key={i}>
                {new Date(l.ts).toLocaleTimeString()} — {l.text} (id: {l.id})
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
