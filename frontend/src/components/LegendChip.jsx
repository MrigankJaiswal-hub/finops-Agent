// frontend/src/components/LegendChip.jsx
import React from "react";

export default function LegendChip({
  text = "Prioritization: actions are ranked by estimated impact ($) and license waste %, with ties broken by negative margin severity."
}) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs bg-white">
      {/* lightning icon */}
      <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-yellow-100">
        <svg viewBox="0 0 24 24" className="h-3 w-3 text-yellow-600" fill="currentColor">
          <path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z" />
        </svg>
      </span>
      <span className="text-gray-700">{text}</span>
    </div>
  );
}
