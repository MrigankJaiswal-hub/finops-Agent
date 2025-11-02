// frontend/src/components/PriorityLegend.jsx
import React from "react";

export default function PriorityLegend() {
  return (
    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs text-gray-700 bg-white">
      <span className="font-medium">How priorities are chosen</span>
      <span className="text-gray-500">
        Rank = high <b>waste%</b> or low/negative <b>margin</b> → highest estimated <b>$ impact</b> first.
      </span>
    </div>
  );
}
