// frontend/src/utils/toastx.js
import toast from "react-hot-toast";

/**
 * Promise wrapper:
 *   tpromise(apiCall(), "Loading...", "Done!", "Failed");
 *
 * Or with options object:
 *   tpromise(apiCall(), {
 *     loading: "Analyzing…",
 *     success: (res) => `Processed ${res.count} rows`,
 *     error: (err) => err?.response?.data?.detail || err.message || "Failed",
 *   })
 */
export function tpromise(promise, loading, success, error) {
  // allow object signature
  const opts =
    typeof loading === "object"
      ? loading
      : { loading, success, error };

  return toast.promise(
    Promise.resolve(promise),
    {
      loading: opts.loading || "Working…",
      success:
        opts.success ||
        ((_) => "Success"),
      error:
        opts.error ||
        ((e) => e?.response?.data?.detail || e?.message || "Something went wrong"),
    }
  );
}

/** Simple helpers */
export const t = {
  ok: (msg) => toast.success(msg),
  err: (msg) => toast.error(msg),
  info: (msg) => toast(msg),
};
