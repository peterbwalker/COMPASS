import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import MedevacMap2D from "./MedevacMap2D.jsx";
import { AdvisorPanel, ComparePanel, ReplayPanel, ScenarioControls } from "./MedevacPanels.jsx";
import { buildModel, clockLabel } from "../medevac/replay.js";
import { medevacAdvisor, medevacCompare, medevacSimulate } from "../api.js";

const MedevacGlobe = lazy(() => import("./MedevacGlobe.jsx"));

const DEFAULT_OPTS = { surge_scale: 1.0, threats_on: true, closures_on: true, c17_count: 3, hospital_ship: true };
const SPEEDS = [2, 6, 12, 24];

function Sparkline({ series, t, tEnd, onScrub }) {
  const W = 400, H = 64;
  const max = Math.max(1, ...series.map((s) => Math.max(s.dead + s.done + s.inSystem, 1)));
  const x = (h) => (h / tEnd) * W;
  const y = (v) => H - 4 - (v / max) * (H - 10);
  const path = (key) => series.map((s, i) => `${i ? "L" : "M"}${x(s.t).toFixed(1)},${y(s[key]).toFixed(1)}`).join("");
  return (
    <svg className="mv-spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none"
      onClick={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        onScrub(((e.clientX - r.left) / r.width) * tEnd);
      }}>
      <path d={path("done")} stroke="#69db7c" />
      <path d={path("inSystem")} stroke="#fcc419" />
      <path d={path("dead")} stroke="#fa5252" />
      <line x1={x(t)} x2={x(t)} y1="0" y2={H} className="mv-cursor" />
    </svg>
  );
}

export default function MedevacView({ apiKey, backendVersion }) {
  const [opts, setOpts] = useState(DEFAULT_OPTS);
  const [policy, setPolicy] = useState("optimized");
  const [seed, setSeed] = useState(1);
  const [change, setChange] = useState(null); // active what-if (advisor interpretation)
  const [sim, setSim] = useState(null);
  const [loadingSim, setLoadingSim] = useState(false);
  const [error, setError] = useState(null);

  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(6);
  const [mapMode, setMapMode] = useState("2d");

  const [tab, setTab] = useState("replay");
  const [nSeeds, setNSeeds] = useState(10);
  const [compare, setCompare] = useState(null);
  const [loadingCompare, setLoadingCompare] = useState(false);
  const [advice, setAdvice] = useState(null);
  const [loadingAdvice, setLoadingAdvice] = useState(false);
  const [adviceError, setAdviceError] = useState(null);

  const model = useMemo(() => (sim ? buildModel(sim) : null), [sim]);

  const runReplay = useCallback(async (over = {}) => {
    const p = over.policy ?? policy;
    const ch = over.change === undefined ? change : over.change;
    setLoadingSim(true);
    setError(null);
    setPlaying(false);
    try {
      const r = await medevacSimulate({
        policy: p, seed: over.seed ?? seed, detail: true,
        scenario: { ...(over.opts ?? opts) },
        change: ch || undefined,
      });
      if (!r || !r.scenario_view) throw new Error("The backend is running an older version (no scenario_view in the response). Pull the latest medevac_routes.py on the server and restart uvicorn.");
      setSim(r);
      setT(0);
      setPlaying(true);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingSim(false);
    }
  }, [policy, seed, opts, change]);

  // First load, and again whenever the backend URL is changed.
  useEffect(() => {
    setSim(null);
    setCompare(null);
    setAdvice(null);
    runReplay();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendVersion]);

  // Playback clock.
  const raf = useRef(null);
  useEffect(() => {
    if (!playing || !model) return undefined;
    let last = performance.now();
    const tick = (now) => {
      const dt = (now - last) / 1000;
      last = now;
      setT((cur) => {
        const nxt = cur + dt * speed;
        if (nxt >= model.tEnd) {
          setPlaying(false);
          return model.tEnd;
        }
        return nxt;
      });
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, model, speed]);

  async function runCompare() {
    setLoadingCompare(true);
    setError(null);
    try {
      setCompare(await medevacCompare({ n_seeds: nSeeds, scenario: opts }));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingCompare(false);
    }
  }

  async function askAdvisor(prompt) {
    setLoadingAdvice(true);
    setAdviceError(null);
    try {
      setAdvice(await medevacAdvisor(prompt, 8));
    } catch (e) {
      setAdviceError(e.message);
    } finally {
      setLoadingAdvice(false);
    }
  }

  function replayWhatIf(interp, bestPolicy) {
    setChange(interp);
    setPolicy(bestPolicy);
    setTab("replay");
    runReplay({ change: interp, policy: bestPolicy });
  }
  function clearWhatIf() {
    setChange(null);
    runReplay({ change: null });
  }

  const st = model ? model.stateAt(t) : null;
  const tq = Math.round(t * (speed >= 12 ? 1 : 4)) / (speed >= 12 ? 1 : 4); // throttle for the 3D layer

  return (
    <div className="mv-body">
      <section className="mv-main">
        <div className="mv-toolbar">
          <div className="mv-seg">
            <button className={mapMode === "2d" ? "on" : ""} onClick={() => setMapMode("2d")}>Tactical map</button>
            <button className={mapMode === "3d" ? "on" : ""} onClick={() => setMapMode("3d")} disabled={!apiKey}
              title={apiKey ? "" : "Enter a Google Maps key in the Logistics tab to enable the 3D globe"}>3D globe</button>
          </div>
          {change && <div className="mv-whatif">what-if active: {change.summary || "custom change"} <button onClick={clearWhatIf}>clear</button></div>}
          <div className="mv-clock">{model ? `${clockLabel(t)} · H+${t.toFixed(0)}` : "—"}</div>
          {st && (
            <div className="mv-hud">
              <span><i style={{ background: "#fcc419" }} />{st.inSystem} in system</span>
              <span><i style={{ background: "#69db7c" }} />{st.done} treated</span>
              <span><i style={{ background: "#fa5252" }} />{st.dead} died</span>
            </div>
          )}
        </div>

        <div className="mv-stage">
          {model && mapMode === "2d" && <MedevacMap2D model={model} t={t} />}
          {model && mapMode === "3d" && apiKey && (
            <Suspense fallback={<div className="mv-center">Loading 3D globe…</div>}>
              <MedevacGlobe apiKey={apiKey} model={model} t={tq} onFail={() => setMapMode("2d")} />
            </Suspense>
          )}
          {!model && <div className="mv-center">{loadingSim ? "Simulating the first scenario…" : error ? `Cannot reach the MEDEVAC backend: ${error}` : "—"}</div>}
          {error && model && <div className="mv-banner">{error}</div>}
          {loadingSim && model && <div className="mv-banner info">Simulating…</div>}
        </div>

        {model && (
          <div className="mv-transport">
            <button className="mv-play" onClick={() => { if (t >= model.tEnd - 0.01) setT(0); setPlaying((p) => !p); }}>
              {playing ? "❚❚" : "▶"}
            </button>
            <input type="range" min="0" max={model.tEnd} step="0.25" value={t}
              onChange={(e) => { setPlaying(false); setT(+e.target.value); }} />
            <select value={speed} onChange={(e) => setSpeed(+e.target.value)} title="Simulated hours per second">
              {SPEEDS.map((s) => <option key={s} value={s}>{s} h/s</option>)}
            </select>
          </div>
        )}

        {model && (
          <div className="mv-lower">
            <div className="mv-spark-wrap">
              <div className="mv-label">Casualties over time <span className="mv-dim">(green treated · amber in system · red died)</span></div>
              <Sparkline series={model.series} t={t} tEnd={model.tEnd} onScrub={(h) => { setPlaying(false); setT(h); }} />
            </div>
            <div className="mv-feed">
              <div className="mv-label">Latest events</div>
              {model.eventsUpTo(t, 6).map((e, i) => (
                <div key={`${e.t}-${i}`} className={`mv-ev ${e.kind}`}><b>H+{e.t.toFixed(0)}</b> {e.text}</div>
              ))}
              {model.eventsUpTo(t, 1).length === 0 && <div className="mv-dim">Nothing yet.</div>}
            </div>
          </div>
        )}
      </section>

      <aside className="mv-side">
        <div className="mv-tabs">
          {[["replay", "Replay"], ["compare", "Compare"], ["advisor", "Advisor"]].map(([k, l]) => (
            <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>
          ))}
        </div>
        <div className="mv-scroll">
          {tab !== "advisor" && <ScenarioControls opts={opts} setOpts={setOpts} disabled={Boolean(change) && tab === "replay"} />}
          {change && tab === "replay" && <div className="mv-hint">Scenario controls are locked while a what-if is active. Clear it to use them.</div>}
          {tab === "replay" && (
            <ReplayPanel sim={sim} policy={policy} setPolicy={setPolicy} seed={seed} setSeed={setSeed}
              onRun={() => runReplay()} loading={loadingSim} />
          )}
          {tab === "compare" && (
            <>
              {change && <div className="mv-hint">Comparison uses the Scenario controls above, not the active what-if. The Advisor tab compares before and after for a what-if.</div>}
              <ComparePanel result={compare} onRun={runCompare} loading={loadingCompare} nSeeds={nSeeds} setNSeeds={setNSeeds} />
            </>
          )}
          {tab === "advisor" && (
            <AdvisorPanel onAsk={askAdvisor} result={advice} loading={loadingAdvice} error={adviceError}
              onReplay={replayWhatIf} onClear={clearWhatIf} active={Boolean(change)} />
          )}
          <div className="mv-foot">Notional scenario: capabilities, rates and threats are placeholders, not validated planning factors.</div>
        </div>
      </aside>
    </div>
  );
}
