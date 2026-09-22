const DEFAULT_BASE_URL = "http://localhost:8000";
const STORAGE_KEY = "compass_backend_url";

// Backend URL is configurable at runtime (not just hardcoded) because
// running the backend on a remote GPU server behind an ngrok/cloudflared
// tunnel means this URL changes every session -- editing source and
// rebuilding each time would be a real workflow drag. Defaults to plain
// localhost for the common case of running the backend locally.
export function getBaseUrl() {
  return localStorage.getItem(STORAGE_KEY) || DEFAULT_BASE_URL;
}

export function setBaseUrl(url) {
  // Strip a trailing slash so `${base}/api/...` never ends up with `//api`.
  const cleaned = url.trim().replace(/\/+$/, "");
  localStorage.setItem(STORAGE_KEY, cleaned);
}

export async function fetchScenario() {
  const res = await fetch(`${getBaseUrl()}/api/scenario`);
  if (!res.ok) throw new Error(`GET /api/scenario failed: ${res.status}`);
  return res.json();
}

export async function fetchStep(step, forceRefresh = false) {
  const res = await fetch(`${getBaseUrl()}/api/step`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ step, force_refresh: forceRefresh }),
  });
  if (!res.ok) throw new Error(`POST /api/step failed: ${res.status}`);
  return res.json();
}
