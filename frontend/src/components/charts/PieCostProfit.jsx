// frontend/src/components/charts/PieCostProfit.jsx
import React, { useMemo, useRef } from "react";
import { Pie } from "react-chartjs-2";
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
} from "chart.js";
import { toast } from "react-hot-toast";
import { copyChartPNG, downloadChartPNG } from "../../utils/chartExport";

ChartJS.register(ArcElement, Tooltip, Legend);

export default function PieCostProfit({ totalRevenue = 0, totalCost = 0 }) {
  const chartRef = useRef(null);

  const { labels, values, colors } = useMemo(() => {
    const profit = totalRevenue - totalCost;
    let lbls = [];
    let vals = [];
    let cols = [];

    if (profit >= 0) {
      lbls = ["Cost", "Profit"];
      vals = [Math.max(totalCost, 0), Math.max(profit, 0)];
      cols = ["#60A5FA", "#34D399"]; // blue cost, green profit
    } else {
      lbls = ["Cost", "Loss (negative profit)"];
      vals = [Math.max(totalCost, 0), Math.abs(profit)];
      cols = ["#60A5FA", "#F87171"]; // blue cost, red loss
    }

    return { labels: lbls, values: vals, colors: cols };
  }, [totalRevenue, totalCost]);

  const data = {
    labels,
    datasets: [
      {
        label: "Cost vs Profit/Loss",
        data: values,
        backgroundColor: colors,
        borderColor: "white",
        borderWidth: 2,
      },
    ],
  };

  const onDownload = async () => {
    const t = toast.loading("Preparing PNG…");
    try {
      await downloadChartPNG(chartRef.current, "cost-vs-profit.png");
      toast.success("Downloaded cost-vs-profit.png", { id: t });
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
        <div className="text-sm text-gray-500">Cost vs Profit overview</div>
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

      <Pie
        ref={chartRef}
        data={data}
        options={{
          plugins: {
            legend: { position: "bottom" },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const v = ctx.raw ?? 0;
                  return `${ctx.label}: ${v.toLocaleString(undefined, {
                    style: "currency",
                    currency: "USD",
                  })}`;
                },
              },
            },
          },
        }}
      />
    </div>
  );
}
