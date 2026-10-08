import { useState } from "react";

const POLICY_LABEL = { stovepipe: "Stovepipe", joint: "Joint pooled", optimized: "Optimized" };
const POLICY_DESC = {
  stovepipe: "Organic lift only; patients go to a same-service facility first.",
  joint: "Lift pooled across services; fastest destination wins.",
  optimized: "Pooled lift plus cost-based routing, queue awareness and batching.",
};
const POLICY_COLOR = { stovepipe: "#868e96", joint: "#4dabf7", optimized: "#efb428" };

export const pct = (x, d = 1) => (x === null || x === undefined ? "—" : `${(x * 100).toFixed(d)}%`);
export const num = (x, d = 1) => (x === null || x === undefined ? "—" : Number(x).toFixed(d));
const signed = (x, d = 1) => (x === null || x === undefined ? "—" : `${x >= 0 ? "+" : ""}${Number(x).toFixed(d)}`);

export function ScenarioControls({ opts, setOpts, disabled }) {
  const set = (k, v) => setOpts({ ...opts, [k]: v });
  return (
    <div className="mv-card">
      <div className="mv-label">Scenario</div>
      <label className="mv-row">
        <span>Casualty surge ×{opts.surge_scale.toFixed(1)}</span>
        <input type="range" min="0.5" max="2.5" step="0.1" value={opts.surge_scale} disabled={disabled}
          onChange={(e) => set("surge_scale", +e.target.value)} />
      </label>
      <label className="mv-row">
        <span>Strategic aeromedical aircraft</span>
        <select value={opts.c17_count} disabled={disabled} onChange={(e) => set("c17_count", +e.target.value)}>
          {[0, 1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </label>
      <div className="mv-checks">
        <label><input type="checkbox" checked={opts.threats_on} disabled={disabled} onChange={(e) => set("threats_on", e.target.checked)} /> threats</label>
        <label><input type="checkbox" checked={opts.closures_on} disabled={disabled} onChange={(e) => set("closures_on", e.target.checked)} /> closures</label>
        <label><input type="checkbox" checked={opts.hospital_ship} disabled={disabled} onChange={(e) => set("hospital_ship", e.target.checked)} /> hospital ship</label>
      </div>
    </div>
  );
}

function Kpi({ label, value, sub, tone }) {
  return (
    <div className={`mv-kpi ${tone || ""}`}>
      <div className="mv-kpi-v">{value}</div>
      <div className="mv-kpi-l">{label}</div>
      {sub && <div className="mv-kpi-s">{sub}</div>}
    </div>
  );
}

export function ReplayPanel({ sim, policy, setPolicy, seed, setSeed, onRun, loading }) {
  const m = sim?.metrics;
  const causes = m ? Object.entries(m.death_causes).sort((a, b) => b[1] - a[1]) : [];
  const maxC = causes.length ? causes[0][1] : 1;
  return (
    <div>
      <div className="mv-card">
        <div className="mv-label">Policy</div>
        <div className="mv-chips">
          {Object.keys(POLICY_LABEL).map((p) => (
            <button key={p} className={`mv-chip ${policy === p ? "on" : ""}`} onClick={() => setPolicy(p)} title={POLICY_DESC[p]}>
              <i style={{ background: POLICY_COLOR[p] }} />{POLICY_LABEL[p]}
            </button>
          ))}
        </div>
        <div className="mv-hint">{POLICY_DESC[policy]}</div>
        <div className="mv-row">
          <span>Random seed</span>
          <input type="number" className="mv-num" value={seed} min={1} onChange={(e) => setSeed(Math.max(1, +e.target.value || 1))} />
          <button className="mv-btn" onClick={onRun} disabled={loading}>{loading ? "Simulating…" : "Run replay"}</button>
        </div>
      </div>

      {m && (
        <div className="mv-card">
          <div className="mv-label">Outcome · {POLICY_LABEL[sim.policy]} · seed {sim.seed}</div>
          <div className="mv-kpis">
            <Kpi label="mortality" value={pct(m.mortality)} sub={`${m.deaths} of ${m.n_casualties}`} tone="bad" />
            <Kpi label="surgery ≤ 6 h" value={pct(m.pct_dcs_within_6h, 0)} sub={`${m.dcs_patients} needing DCS`} />
            <Kpi label="median to surgery" value={`${num(m.time_to_surgery_h.median)} h`} sub={`p90 ${num(m.time_to_surgery_h.p90)} h`} />
            <Kpi label="median to Role 4" value={`${num(m.time_to_r4_h.median, 0)} h`} sub={`p90 ${num(m.time_to_r4_h.p90, 0)} h`} />
            <Kpi label="missions lost" value={`${m.missions_lost}`} sub={`of ${m.missions}`} tone={m.missions_lost ? "warn" : ""} />
            <Kpi label="cross-service legs" value={pct(m.interservice_leg_share, 0)} sub={`mean load ${num(m.mean_load)}`} />
          </div>
          <div className="mv-label" style={{ marginTop: 10 }}>Where the deaths happened</div>
          {causes.map(([k, v]) => (
            <div key={k} className="mv-bar">
              <span>{k.toLowerCase().replace(/_/g, " ")}</span>
              <div><i style={{ width: `${(v / maxC) * 100}%` }} /></div>
              <b>{v}</b>
            </div>
          ))}
          {m.unresolved_at_end > 0 && <div className="mv-hint">{m.unresolved_at_end} patient(s) still in the system at the end of the run.</div>}
        </div>
      )}
    </div>
  );
}

function CiRow({ name, color, stat, scale, fmt }) {
  const lo = stat.ci95 ? stat.ci95[0] : stat.mean;
  const hi = stat.ci95 ? stat.ci95[1] : stat.mean;
  return (
    <div className="mv-ci">
      <span><i style={{ background: color }} />{name}</span>
      <div className="mv-ci-track">
        <div className="mv-ci-bar" style={{ width: `${(stat.mean / scale) * 100}%`, background: color }} />
        <div className="mv-ci-whisker" style={{ left: `${(Math.max(0, lo) / scale) * 100}%`, width: `${((hi - Math.max(0, lo)) / scale) * 100}%` }} />
      </div>
      <b>{fmt(stat.mean)}</b>
    </div>
  );
}

export function ComparePanel({ result, onRun, loading, nSeeds, setNSeeds }) {
  const pols = result ? result.policies : [];
  const scale = result ? Math.max(...pols.map((p) => result.summary[p].mortality.ci95[1])) * 1.1 : 1;
  return (
    <div>
      <div className="mv-card">
        <div className="mv-label">Compare policies</div>
        <div className="mv-hint">Same casualties and same random draws for every policy, so differences are paired by seed.</div>
        <div className="mv-row">
          <span>Replications</span>
          <select value={nSeeds} onChange={(e) => setNSeeds(+e.target.value)}>
            {[5, 10, 20, 30].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
          <button className="mv-btn" onClick={onRun} disabled={loading}>{loading ? "Running…" : "Run comparison"}</button>
        </div>
      </div>
      {result && (
        <>
          <div className="mv-card">
            <div className="mv-label">Mortality (mean, 95% interval)</div>
            {pols.map((p) => <CiRow key={p} name={POLICY_LABEL[p]} color={POLICY_COLOR[p]} stat={result.summary[p].mortality} scale={scale} fmt={(x) => pct(x)} />)}
          </div>
          <div className="mv-card">
            <div className="mv-label">Other measures (mean)</div>
            <table className="mv-table">
              <thead><tr><th />{pols.map((p) => <th key={p}>{POLICY_LABEL[p]}</th>)}</tr></thead>
              <tbody>
                {[
                  ["surgery ≤ 6 h", (s) => pct(s.pct_dcs_within_6h.mean, 0)],
                  ["median to surgery (h)", (s) => num(s.median_time_to_surgery_h.mean)],
                  ["median to Role 4 (h)", (s) => num(s.median_time_to_r4_h.mean, 0)],
                  ["missions lost", (s) => num(s.missions_lost.mean)],
                  ["mean load", (s) => num(s.mean_load.mean)],
                  ["cross-service legs", (s) => pct(s.interservice_leg_share.mean, 0)],
                ].map(([label, f]) => (
                  <tr key={label}><td>{label}</td>{pols.map((p) => <td key={p}>{f(result.summary[p])}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
          {Object.keys(result.paired_vs_first).length > 0 && (
            <div className="mv-card">
              <div className="mv-label">Paired change in deaths per run</div>
              {Object.entries(result.paired_vs_first).map(([k, v]) => {
                const [a, b] = k.split("_minus_");
                const sig = v.deaths.ci95[1] < 0 || v.deaths.ci95[0] > 0;
                return (
                  <div key={k} className="mv-pair">
                    <b>{POLICY_LABEL[a]}</b> vs {POLICY_LABEL[b]}: <span className={v.deaths.mean < 0 ? "mv-good" : "mv-bad"}>{signed(v.deaths.mean)}</span>
                    <span className="mv-dim"> (95% {signed(v.deaths.ci95[0])} to {signed(v.deaths.ci95[1])}) · fewer deaths in {v.wins} of {v.n} runs{sig ? "" : " · not distinguishable from noise"}</span>
                  </div>
                );
              })}
            </div>
          )}
          <div className="mv-hint">{result.caveat}</div>
        </>
      )}
    </div>
  );
}

const EXAMPLES = [
  "Okinawa closes at hour 30 and we lose two strategic aeromedical aircraft",
  "What if the casualty surge is 50% larger and the hospital ship is not available?",
  "We lose both Navy helicopters in the first day. How do the policies cope?",
];

export function AdvisorPanel({ onAsk, result, loading, error, onReplay, onClear, active }) {
  const [text, setText] = useState("");
  const res = result?.results;
  return (
    <div>
      <div className="mv-card">
        <div className="mv-label">Planner's what-if</div>
        <textarea className="mv-textarea" rows={4} value={text} onChange={(e) => setText(e.target.value)}
          placeholder="Describe a change in plain language, e.g. a closure, lost aircraft, a surge…" />
        <div className="mv-examples">
          {EXAMPLES.map((e) => <button key={e} className="mv-ex" onClick={() => setText(e)}>{e}</button>)}
        </div>
        <button className="mv-btn" disabled={loading || text.trim().length < 3} onClick={() => onAsk(text.trim())}>
          {loading ? "Interpreting and simulating…" : "Ask advisor"}
        </button>
        {error && <div className="mv-error">{error}</div>}
      </div>

      {result && (
        <>
          <div className="mv-card">
            <div className="mv-label">Assessment <span className="mv-tag">{result.narrative_by_llm ? "model-written" : "template summary"}</span></div>
            <div className="mv-narr">{result.narrative}</div>
          </div>
          <div className="mv-card">
            <div className="mv-label">What was changed</div>
            {result.applied.length ? <ul className="mv-list">{result.applied.map((a) => <li key={a}>{a}</li>)}</ul> : <div className="mv-hint">No changes were applied.</div>}
            {result.warnings.length > 0 && <ul className="mv-list warn">{result.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
          </div>
          <div className="mv-card">
            <div className="mv-label">Result by policy (mean over {res.seeds.length} seeds)</div>
            <table className="mv-table">
              <thead><tr><th>policy</th><th>before</th><th>after</th><th>Δ deaths / run</th></tr></thead>
              <tbody>
                {Object.entries(res.policies).map(([p, r]) => (
                  <tr key={p} className={p === res.best_policy_after_change ? "best" : ""}>
                    <td>{POLICY_LABEL[p]}{p === res.best_policy_after_change ? " ★" : ""}</td>
                    <td>{pct(r.baseline.mortality)}</td>
                    <td>{pct(r.changed.mortality)}</td>
                    <td>{signed(r.delta_deaths.mean)} <span className="mv-dim">({signed(r.delta_deaths.ci95[0])}, {signed(r.delta_deaths.ci95[1])})</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mv-actions">
              <button className="mv-btn" onClick={() => onReplay(result.interpretation, res.best_policy_after_change)}>Replay this what-if</button>
              {active && <button className="mv-btn ghost" onClick={onClear}>Clear what-if</button>}
            </div>
            <div className="mv-hint">{result.caveat}</div>
          </div>
        </>
      )}
    </div>
  );
}
