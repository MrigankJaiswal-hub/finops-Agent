//SuperOps mock client list
// frontend/src/pages/Clients.jsx
// frontend/src/pages/Clients.jsx
import React, { useEffect, useState } from "react";
import { useAuth } from "react-oidc-context";
import { getClients } from "../utils/api";

export default function Clients() {
  const auth = useAuth();
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [items, setItems] = useState([]);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      setErr("");
      try {
        const list = await getClients(); // calls /mockclients under the hood
        if (!alive) return;
        setItems(Array.isArray(list) ? list : []);
      } catch (e) {
        if (!alive) return;
        setErr(e?.message || "Failed to load clients");
        setItems([]);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Kiros / SuperOps Clients</h1>

      <div className="text-sm text-gray-600">
        Signed in as <b>{auth?.user?.profile?.email || "guest"}</b>
      </div>

      {loading && (
        <div className="rounded border p-4 bg-gray-50">Loading clients…</div>
      )}

      {!loading && err && (
        <div className="border border-red-200 bg-red-50 text-red-800 p-4 rounded">
          <div className="font-medium">Failed to load clients.</div>
          <div className="text-sm mt-1 whitespace-pre-wrap">{String(err)}</div>
        </div>
      )}

      {!loading && !err && items.length === 0 && (
        <div className="text-gray-600">
          No clients found. (If /mockclients is disabled, this can be empty.)
        </div>
      )}

      {!loading && !err && items.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {items.map((c, idx) => (
            <div key={`${c?.name || "client"}-${idx}`} className="border rounded-lg p-4">
              <div className="font-semibold text-blue-700">{c?.name || "Client"}</div>
              <div className="text-sm mt-1">Region: {c?.region || "—"}</div>
              <div className="text-sm">Contracts: {c?.contracts ?? "—"}</div>
              <div className="text-sm">Tickets Open: {c?.tickets_open ?? "—"}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
