import { useEffect, useState } from "react";
import Globe3D from "./components/Globe3D.jsx";
import Timeline from "./components/Timeline.jsx";
import CoaPanel from "./components/CoaPanel.jsx";
import { fetchScenario, fetchStep } from "./api.js";

export default function App() {
  const [apiKey, setApiKey] = useState(
    () => localStorage.getItem("gmaps_api_key_input") || ""
  );
  const [apiKeyDraft, setApiKeyDraft] = useState(apiKey);

  const [scenario, setScenario] = useState(null); // { nodes, routes, num_steps }
  const [step, setStep] = useState(0);
  const [stepData, setStepData] = useState(null); // result of POST /api/step
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [highlightedRouteIds, setHighlightedRouteIds] = useState([]);

  // Note: this stores the key in the browser's localStorage for dev
  // convenience only, so you don't retype it every reload while
  // iterating. Don't reuse this pattern for anything beyond local
  // prototyping on your own machine.
  useEffect(() => {
    fetchScenario()
      .then(setScenario)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!scenario) return;
    setLoading(true);
    setError(null);
    fetchStep(step)
      .then(setStepData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [step, scenario]);

  function handleSaveKey() {
    localStorage.setItem("gmaps_api_key_input", apiKeyDraft);
    setApiKey(apiKeyDraft);
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="wordmark">
          COMPASS<span>contested logistics decision support</span>
        </div>
        <div className="step-readout">
          {scenario ? `${scenario.num_steps} timesteps loaded` : "connecting to backend…"}
          {error && ` — error: ${error}`}
        </div>
      </header>

      <div className="globe-pane">
        {!apiKey ? (
          <div className="globe-key-prompt">
            <p>
              Enter a Google Maps Platform API key with the Maps JavaScript
              API (and Map Tiles / Photorealistic 3D Maps) enabled to render
              the live globe.
            </p>
            <input
              type="password"
              placeholder="AIza..."
              value={apiKeyDraft}
              onChange={(e) => setApiKeyDraft(e.target.value)}
            />
            <button onClick={handleSaveKey}>Load globe</button>
          </div>
        ) : (
          scenario && (
            <Globe3D
              apiKey={apiKey}
              nodes={scenario.nodes}
              routes={stepData?.snapshot?.routes || scenario.routes}
              highlightedRouteIds={highlightedRouteIds}
            />
          )
        )}
      </div>

      <aside className="sidebar">
        {scenario && (
          <Timeline step={step} numSteps={scenario.num_steps} onChange={setStep} />
        )}
        <div className="panel-scroll">
          <CoaPanel stepData={stepData} loading={loading} onHoverCoa={setHighlightedRouteIds} />
        </div>
        <div className="route-legend">
          <span>
            <span className="swatch" style={{ background: "#4a9b6e" }} />
            open
          </span>
          <span>
            <span className="swatch" style={{ background: "#d98e2b" }} />
            contested
          </span>
          <span>
            <span className="swatch" style={{ background: "#c1443c" }} />
            closed
          </span>
        </div>
      </aside>
    </div>
  );
}
