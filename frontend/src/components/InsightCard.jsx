import React from "react";

const InsightCard = ({ insight }) => {
  const { client, revenue, cost, margin, license_waste_pct, health } = insight;
  return (
    <div className="p-4 border rounded-xl bg-white shadow-sm hover:shadow-md transition">
      <h3 className="font-semibold text-lg mb-2 text-blue-700">{client}</h3>
      <p className="text-sm">Revenue: ${revenue}</p>
      <p className="text-sm">Cost: ${cost}</p>
      <p className="text-sm">Margin: ${margin}</p>
      <p className="text-sm">
        License Waste: {license_waste_pct}% |{" "}
        <span
          className={`font-medium ${
            health === "At Risk"
              ? "text-red-600"
              : health === "Inefficient"
              ? "text-yellow-600"
              : "text-green-600"
          }`}
        >
          {health}
        </span>
      </p>
    </div>
  );
};

export default InsightCard;
