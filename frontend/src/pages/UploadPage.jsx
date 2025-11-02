// frontend/src/pages/UploadPage.jsx
// Upload page that ensures you're authenticated and a Bearer token exists
// before calling /upload. Shows a preview of the first bytes and friendly errors.

import React, { useState } from "react";
import { useAuth } from "react-oidc-context";
import { uploadCSV, addLocalHistory } from "../utils/api";

export default function UploadPage() {
  const auth = useAuth();
  const [file, setFile] = useState(null);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState("");

  const onFile = (f) => {
    setFile(f || null);
    setRes(null);
    setErr("");
    setPreview("");
    if (f) {
      const reader = new FileReader();
      reader.onload = () => {
        const txt = String(reader.result || "");
        setPreview(txt.slice(0, 256));
      };
      reader.readAsText(f);
    }
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setErr("");
    setRes(null);

    if (!file) {
      setErr("Please choose a CSV file.");
      return;
    }

    if (!auth.isAuthenticated) {
      auth.signinRedirect();
      return;
    }

    try {
      setLoading(true);
      console.log("[Upload] starting:", file.name, "type:", file.type, "size:", file.size);
      const data = await uploadCSV(file); // axios helper; DO NOT set Content-Type manually
      setRes(data);

      // Remember the saved key locally so AIInsights dropdown can see it
      if (data?.stored_key && typeof data.stored_key === "string") {
        addLocalHistory(data.stored_key);
      }
    } catch (ex) {
      const msg =
        ex?.response?.data?.detail ||
        ex?.response?.statusText ||
        ex?.message ||
        "Upload failed";
      setErr(String(msg));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Upload Billing CSV</h1>

      {!auth.isAuthenticated ? (
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 p-4 rounded">
          You’re not signed in. Please{" "}
          <button className="underline" onClick={() => auth.signinRedirect()}>
            sign in
          </button>{" "}
          to upload.
        </div>
      ) : (
        <div className="text-sm text-gray-600">
          Signed in as <b>{auth.user?.profile?.email || "user"}</b>
        </div>
      )}

      <div className="text-sm text-gray-500">
        Try sample CSVs:{" "}
        <a className="text-blue-600 underline" href="/api/sample-csv/balanced">Balanced</a>{" "}
        |{" "}
        <a className="text-blue-600 underline" href="/api/sample-csv/waste">High Waste</a>{" "}
        |{" "}
        <a className="text-blue-600 underline" href="/api/sample-csv/aws">AWS-Style Fallback</a>
      </div>

      <form onSubmit={onSubmit} className="space-y-4 bg-white rounded-xl shadow p-5">
        <div className="border-2 border-dashed rounded-lg p-4">
          <div className="text-sm text-gray-600 mb-2">
            Drag &amp; drop your <b>CSV</b> here, or choose a file:
          </div>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => onFile(e.target.files?.[0] || null)}
          />
          {preview && (
            <pre className="mt-3 text-xs text-gray-600 whitespace-pre-wrap">
{preview}
            </pre>
          )}
        </div>
        <button
          type="submit"
          disabled={loading || !file}
          className="px-3 py-1.5 rounded bg-blue-600 text-white disabled:opacity-60"
        >
          {loading ? "Uploading…" : "Upload & Analyze"}
        </button>

        {err && <div className="text-red-600">{err}</div>}
      </form>

      {res && (
        <div className="bg-white rounded-xl shadow p-5">
          <h2 className="text-lg font-semibold mb-3">Analysis Result</h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <Stat label="Total Revenue" value={money(res.total_revenue)} />
            <Stat label="Total Cost" value={money(res.total_cost)} />
            <Stat label="Total Profit" value={money(res.total_profit)} />
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left border-b">
                  <th className="py-2 pr-4">Client</th>
                  <th className="py-2 pr-4">Revenue</th>
                  <th className="py-2 pr-4">Cost</th>
                  <th className="py-2 pr-4">Margin</th>
                  <th className="py-2 pr-4">Waste %</th>
                  <th className="py-2 pr-4">Health</th>
                </tr>
              </thead>
              <tbody>
                {(res.client_insights || []).map((c, i) => (
                  <tr key={i} className="border-b last:border-none">
                    <td className="py-2 pr-4">{c.client}</td>
                    <td className="py-2 pr-4">{money(c.revenue)}</td>
                    <td className="py-2 pr-4">{money(c.cost)}</td>
                    <td className="py-2 pr-4">{money(c.margin)}</td>
                    <td className="py-2 pr-4">{pct(c.license_waste_pct)}</td>
                    <td className="py-2 pr-4">{c.health}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {res.stored_key && (
            <div className="text-xs text-gray-500 mt-2">
              Saved to S3 as <code>{res.stored_key}</code>
            </div>
          )}
        </div>
      )}
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
