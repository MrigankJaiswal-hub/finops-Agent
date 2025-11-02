// frontend/src/components/charts/MarginBar.jsx
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

export default function MarginBar({ clientInsights = [], topN = 8 }) {
  const chartRef = useRef(null);

  const { labels, values, colors } = useMemo(() => {
    const sorted = [...clientInsights].sort(
      (a, b) => Math.abs(b.margin || 0) - Math.abs(a.margin || 0)
    );
    const pick = sorted.slice(0, topN);

    const lbls = pick.map((c) => c.client);
    const vals = pick.map((c) => Number(c.margin || 0));

    // color code: negative margin -> red; positive -> green; near-zero -> amber
    const cols = vals.map((v) =>
      v < 0 ? "#F87171" : v > 50 ? "#34D399" : "#FBBF24"
    );
    return { labels: lbls, values: vals, colors: cols };
  }, [clientInsights, topN]);

  const data = {
    labels,
    datasets: [
      {
        label: "Margin ($)",
        data: values,
        backgroundColor: colors,
        borderWidth: 1,
      },
    ],
  };

  const onDownload = async () => {
    const t = toast.loading("Preparing PNG…");
    try {
      await downloadChartPNG(chartRef.current, "client-margins.png");
      toast.success("Downloaded client-margins.png", { id: t });
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
        <div className="text-sm text-gray-500">
          Top clients by absolute margin (focus areas)
        </div>
        <div className="flex gap-2">
          <button
            className="px-2.5 py-1 text-xs rounded bg-gray-900 text-white"
            onClick={onDownload}
            title="Download PNG"
          >
            ⬇️ PNG
          </button>
          <button
            className="px-2.5 py-1 text-xs rounded bg-violet-600 text-white"
            onClick={onCopy}
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
          responsive: true,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const v = ctx.raw ?? 0;
                  return `Margin: ${v.toLocaleString(undefined, {
                    style: "currency",
                    currency: "USD",
                  })}`;
                },
              },
            },
          },
          scales: {
            y: {
              ticks: {
                callback: (v) =>
                  Number(v).toLocaleString(undefined, {
                    style: "currency",
                    currency: "USD",
                    maximumFractionDigits: 0,
                  }),
              },
              grid: { color: "#eee" },
            },
            x: { grid: { display: false } },
          },
        }}
      />
    </div>
  );
}
