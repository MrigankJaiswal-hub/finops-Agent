// frontend/src/pages/AdminBudgets.jsx
import React, { useEffect, useState, useMemo } from "react";
import { toast } from "react-hot-toast";
import { useAuth } from "react-oidc-context";

// Use the helpers you already have in utils/api.js
import { getBudgets, saveBudgets } from "../utils/api";

export default function AdminBudgets() {
  const auth = useAuth();
  const email = auth?.user?.profile?.email || "guest";

  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [budgets, setBudgets] = useState({}); // { "ClientA": 5000, ... }

  const isAuthed = !!auth?.isAuthenticated && !auth?.isLoading;

  const load = async () => {
    setLoading(true);
    setErr("");
    try {
      const m = await getBudgets({ _ts: Date.now() }); // GET /budgets
      setBudgets(m || {});
    } catch (e) {
      const message =
        e?.response?.status === 401 || e?.response?.status === 403
          ? "Please sign in to manage budgets (admin)."
          : e?.response?.data?.detail || e?.message || "Admin budgets fetch failed";
      setErr(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // wait for OIDC to resolve, then load
    if (!auth?.isLoading) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth?.isLoading, auth?.isAuthenticated]);

  const entries = useMemo(() => Object.keys(budgets || {}).sort(), [budgets]);

  const updateCell = (client, val) => {
    setBudgets((prev) => {
      const v = val === "" ? "" : Math.max(0, Number(val) || 0);
      return { ...(prev || {}), [client]: v };
    });
  };

  const addClient = () => {
    const name = prompt("Client name?");
    if (!name) return;
    setBudgets((prev) => ({ ...(prev || {}), [name]: "" }));
  };

  const removeClient = (client) => {
    const ok = confirm(`Remove budget row for "${client}"?`);
    if (!ok) return;
    setBudgets((prev) => {
      const next = { ...(prev || {}) };
      delete next[client];
      return next;
    });
  };

  const saveAll = async () => {
    setLoading(true);
    setErr("");
    try {
      await saveBudgets(budgets); // POST /budgets (whole object)
      toast.success("Budgets saved");
      await load();
    } catch (e) {
      const message =
        e?.response?.status === 401 || e?.response?.status === 403
          ? "You are not authorized to save budgets. Please sign in."
          : e?.response?.data?.detail || e?.message || "Failed to save budgets";
      setErr(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Admin • Budgets</h1>
        <div className="text-sm text-gray-500 flex items-center gap-2">
          <span>
            You: <b>{email}</b>
          </span>
          <button
            className="px-3 py-1.5 rounded bg-gray-800 text-white disabled:opacity-60"
            onClick={load}
            disabled={loading}
          >
            Refresh
          </button>
          <button
            className="px-3 py-1.5 rounded bg-blue-600 text-white disabled:opacity-60"
            onClick={saveAll}
            disabled={loading || !isAuthed}
            title={isAuthed ? "Save all budgets" : "Sign in to save budgets"}
          >
            Save All
          </button>
          <button
            className="px-3 py-1.5 rounded bg-gray-100 disabled:opacity-60"
            onClick={addClient}
            disabled={loading}
          >
            Add Client
          </button>
        </div>
      </div>

      {!isAuthed && (
        <div className="rounded border p-3 bg-yellow-50 text-yellow-900 text-sm">
          You are not signed in. You can edit locally in the table, but{" "}
          <b>saving to server requires signing in</b>.
        </div>
      )}

      {!!err && (
        <div className="rounded border border-red-200 bg-red-50 text-red-800 p-3">{err}</div>
      )}

      <div className="rounded border bg-white p-4">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr className="text-left">
              <th className="px-3 py-2 w-2/3">Client</th>
              <th className="px-3 py-2 w-1/3">Budget ($)</th>
              <th className="px-3 py-2 w-24"></th>
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 && (
              <tr>
                <td className="px-3 py-3 text-gray-500" colSpan={3}>
                  No budgets set. Use <b>Add Client</b> to create rows.
                </td>
              </tr>
            )}
            {entries.map((client) => (
              <tr key={client} className="border-t">
                <td className="px-3 py-2">{client}</td>
                <td className="px-3 py-2">
                  <input
                    className="border rounded px-2 py-1 text-sm w-36"
                    value={budgets[client]}
                    onChange={(e) => updateCell(client, e.target.value)}
                    inputMode="numeric"
                    placeholder="e.g. 5000"
                  />
                </td>
                <td className="px-3 py-2">
                  <button
                    className="px-2 py-1 rounded bg-red-50 text-red-700 border border-red-200"
                    onClick={() => removeClient(client)}
                    disabled={loading}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="text-xs text-gray-500">
        Admin budgets editor uses <code>GET /budgets</code> and <code>POST /budgets</code>.
      </div>
    </div>
  );
}
