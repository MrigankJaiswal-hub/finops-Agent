// frontend/src/components/charts/WasteBar.jsx
import React, { useMemo, useRef } from "react";
import { Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
} from "chart.js";
import { toast } from "react-hot-toast";
import { copyChartPNG, downloadChartPNG } from "../../utils/chartExport";

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend);

export default function WasteBar({ clientInsights = [], topN = 10, title = "Waste % by Client" }) {
  const chartRef = useRef(null);

  const { labels, values, colors, suggestedMax } = useMemo(() => {
    const sorted = [...clientInsights]
      .filter((c) => Number.isFinite(Number(c.license_waste_pct)))
      .sort((a, b) => Number(b.license_waste_pct || 0) - Number(a.license_waste_pct || 0))
      .slice(0, topN);

    const lbls = sorted.map((c) => c.client);
    const vals = sorted.map((c) => Number(c.license_waste_pct || 0));

    // color: >=30% -> red, 10-30 -> amber, <10 -> green
    const cols = vals.map((v) =>
      v >= 30 ? "#F87171" : v >= 10 ? "#FBBF24" : "#34D399"
    );

    const max = Math.max(40, ...vals, 0);
    return { labels: lbls, values: vals, colors: cols, suggestedMax: max };
  }, [clientInsights, topN]);

  const data = {
    labels,
    datasets: [
      {
        label: "Waste %",
        data: values,
        backgroundColor: colors,
        borderWidth: 1,
      },
    ],
  };

  const onDownload = async () => {
    const t = toast.loading("Preparing PNG…");
    try {
      await downloadChartPNG(chartRef.current, "waste-by-client.png");
      toast.success("Downloaded waste-by-client.png", { id: t });
    } catch (e) {
      toast.error(e?.message || "Download failed", { id: t });
    }
  };

  const onCopy = async () => {
    const t = toast.loading("Copying PNG…");
    try {
      const mode = await copyChartPNG(chartRef.current);
      if (mode === "copied") {
        toast.success("Copied to clipboard ✔️", { id: t });
      } else {
        toast.success("Clipboard unsupported — downloaded instead", { id: t });
      }
    } catch (e) {
      toast.error(e?.message || "Copy failed", { id: t });
    }
  };

  return (
    <div className="p-4 rounded border">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm text-gray-500">{title}</div>
        <div className="flex gap-2">
          <button
            onClick={onDownload}
            className="text-xs px-2 py-1 rounded bg-gray-900 text-white"
            title="Download chart as PNG"
          >
            ⬇️ PNG
          </button>
          <button
            onClick={onCopy}
            className="text-xs px-2 py-1 rounded bg-violet-600 text-white"
            title="Copy PNG to clipboard"
          >
            📋 Copy
          </button>
        </div>
      </div>

      <Bar
        ref={chartRef}
        data={data}
        options={{
          indexAxis: "y", // horizontal
          responsive: true,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const v = ctx.raw ?? 0;
                  return `Waste: ${v.toFixed(1)}%`;
                },
              },
            },
          },
          scales: {
            x: {
              ticks: {
                callback: (v) => `${Number(v).toFixed(0)}%`,
              },
              grid: { color: "#eee" },
              min: 0,
              suggestedMax, // adaptive headroom
            },
            y: { grid: { display: false } },
          },
        }}
      />
    </div>
  );
}
