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
  const res = await fetch(`${getBaseUrl()}/api/scenario`, {
    // ngrok's abuse-prevention interstitial doesn't see cookies from a
    // direct browser visit on a cross-origin fetch() call, so it can
    // still intercept programmatic requests and return its own page
    // with no CORS headers at all -- this header tells it to skip that.
    // Harmless no-op against a plain localhost backend or cloudflared.
    headers: { "ngrok-skip-browser-warning": "true" },
  });
  if (!res.ok) throw new Error(`GET /api/scenario failed: ${res.status}`);
  return res.json();
}

export async function fetchStep(step, forceRefresh = false, userPrompt = null) {
  const res = await fetch(`${getBaseUrl()}/api/step`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "ngrok-skip-browser-warning": "true",
    },
    body: JSON.stringify({ step, force_refresh: forceRefresh, user_prompt: userPrompt }),
  });
  if (!res.ok) throw new Error(`POST /api/step failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------- MEDEVAC
// Same backend, same tunnel, same ngrok header. Errors carry the server's
// `detail` message when there is one (e.g. "Advisor needs ANTHROPIC_API_KEY").
async function medevacRequest(path, body) {
  const res = await fetch(`${getBaseUrl()}${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "Content-Type": "application/json",
      "ngrok-skip-browser-warning": "true",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = "";
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`${path} failed (${res.status})${detail ? `: ${detail}` : ""}`);
  }
  return res.json();
}

export const medevacScenario = () => medevacRequest("/api/medevac/scenario");
export const medevacSimulate = (body) => medevacRequest("/api/medevac/simulate", body);
export const medevacCompare = (body) => medevacRequest("/api/medevac/compare", body);
export const medevacAdvisor = (prompt, nSeeds = 8) =>
  medevacRequest("/api/medevac/advisor", { prompt, n_seeds: nSeeds });
