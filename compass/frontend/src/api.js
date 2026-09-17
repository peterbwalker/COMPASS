const BASE_URL = "http://localhost:8000";

export async function fetchScenario() {
  const res = await fetch(`${BASE_URL}/api/scenario`);
  if (!res.ok) throw new Error(`GET /api/scenario failed: ${res.status}`);
  return res.json();
}

export async function fetchStep(step) {
  const res = await fetch(`${BASE_URL}/api/step`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ step }),
  });
  if (!res.ok) throw new Error(`POST /api/step failed: ${res.status}`);
  return res.json();
}
