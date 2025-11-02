// frontend/src/utils/chartExport.js
// Utilities to export a react-chartjs-2 chart to PNG (download or clipboard)

export async function chartToBlob(chart, mime = "image/png") {
  if (!chart) throw new Error("Chart ref is not ready");
  // Chart.js instance exposes toBase64Image()
  const dataUrl = chart.toBase64Image(mime, 1.0);
  const res = await fetch(dataUrl);
  return await res.blob();
}

export async function downloadChartPNG(chart, filename = "chart.png") {
  const blob = await chartToBlob(chart);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function copyChartPNG(chart) {
  const blob = await chartToBlob(chart);

  // Clipboard API (secure context: https / localhost)
  const canClipboard =
    navigator.clipboard &&
    typeof window.ClipboardItem !== "undefined" &&
    window.isSecureContext !== false;

  if (canClipboard) {
    const item = new ClipboardItem({ [blob.type]: blob });
    await navigator.clipboard.write([item]);
    return "copied";
  }

  // Fallback: trigger a download instead
  await downloadChartPNG(chart, "chart.png");
  return "downloaded";
}
