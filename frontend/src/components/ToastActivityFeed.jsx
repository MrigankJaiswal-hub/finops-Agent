// src/components/ToastActivityFeed.jsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { useToasterStore } from "react-hot-toast";

/**
 * A tiny activity feed that tracks toast create/dismiss events.
 * No use of toast.onChange (not available) — we rely on useToasterStore().
 */
export default function ToastActivityFeed({ limit = 6 }) {
  const { toasts } = useToasterStore(); // reactive array of toast objects
  const [events, setEvents] = useState([]);
  const prevIdsRef = useRef(new Set());

  // detect created & dismissed by diff'ing toast IDs
  useEffect(() => {
    const currentIds = new Set(toasts.map((t) => t.id));
    const prevIds = prevIdsRef.current;

    // created
    for (const t of toasts) {
      if (!prevIds.has(t.id)) {
        setEvents((e) =>
          [
            {
              kind: "created",
              id: t.id,
              type: t.type, // 'success' | 'error' | 'loading' | 'blank'
              ts: Date.now(),
              message: extractText(t.message),
            },
            ...e,
          ].slice(0, limit)
        );
      }
    }

    // dismissed
    for (const id of prevIds) {
      if (!currentIds.has(id)) {
        setEvents((e) =>
          [
            {
              kind: "dismissed",
              id,
              ts: Date.now(),
            },
            ...e,
          ].slice(0, limit)
        );
      }
    }

    prevIdsRef.current = currentIds;
  }, [toasts, limit]);

  const rows = useMemo(() => events, [events]);

  if (!rows.length) return null;

  return (
    <div className="rounded border p-3 bg-white/60">
      <div className="text-sm font-semibold mb-2">Recent activity</div>
      <ul className="space-y-1 text-xs text-gray-700">
        {rows.map((e) => (
          <li key={`${e.kind}-${e.id}-${e.ts}`} className="flex items-center gap-2">
            <span className="inline-flex h-2 w-2 rounded-full"
              style={{ background: e.kind === "created" ? "#22c55e" : "#ef4444" }}
              title={e.kind}
            />
            <span className="font-medium">{e.kind === "created" ? "Toast" : "Dismissed"}</span>
            <code className="px-1 bg-gray-100 rounded">{e.id.slice(0, 6)}</code>
            {e.kind === "created" && e.type ? (
              <span className="text-gray-500">({e.type})</span>
            ) : null}
            {e.message ? <span className="truncate max-w-[280px]">— {e.message}</span> : null}
            <span className="ml-auto text-[10px] text-gray-400">
              {new Date(e.ts).toLocaleTimeString()}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Try to stringify toast message if it's a ReactNode
function extractText(msg) {
  if (!msg) return "";
  if (typeof msg === "string") return msg;
  try {
    // react-hot-toast often stores message in .props?.children for JSX
    if (msg?.props?.children) {
      if (Array.isArray(msg.props.children)) {
        return msg.props.children.filter(Boolean).join(" ");
      }
      return String(msg.props.children);
    }
    return String(msg);
  } catch {
    return "";
  }
}
