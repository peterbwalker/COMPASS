import { useMemo, useRef, useState } from "react";
import landPath from "../medevac/landPath.js";
import {
  ACUITY_COLOR, ACUITY_ORDER, ACUITY_LABEL, KM_PER_DEG, SERVICE_COLOR, project, viewBox,
} from "../medevac/proj.js";

const VEHICLE_SIZE = { ROTARY: 0.3, TILTROTOR: 0.34, FIXED_WING: 0.42, STRAT_AE: 0.55, SURFACE: 0.36 };
const ROLE_OFFSET = { 1: [-0.34, 0.22], 2: [0, 0], 3: [0, 0] };

function worstColor(counts) {
  for (let i = 0; i < 4; i++) if (counts[i] > 0) return ACUITY_COLOR[ACUITY_ORDER[i]];
  return "#6c7a89";
}

/**
 * Offline-capable tactical map: coastlines are bundled, so this works with no
 * Google key. Shows facilities (by Role), threat envelopes, closures, every
 * in-flight mission, patient counts per site and recent deaths at time t.
 */
export default function MedevacMap2D({ model, t }) {
  const base0 = useMemo(() => viewBox(), []);
  const [vb, setVb] = useState(base0);
  const [hover, setHover] = useState(null);
  const drag = useRef(null);
  const svgRef = useRef(null);

  const state = useMemo(() => model.stateAt(t), [model, t]);
  const missions = useMemo(() => model.missionsAt(t), [model, t]);
  const activeThreats = useMemo(() => new Set(model.threatsActive(t)), [model, t]);
  const closed = useMemo(() => new Set(model.closedAt(t)), [model, t]);
  const view = model.view;

  const facPos = (f) => {
    const [x, y] = project(f.lat, f.lon);
    const [dx, dy] = ROLE_OFFSET[f.role] || [0, 0];
    return [x + dx, y + dy];
  };
  const nodePos = (n) => (n.role ? facPos(n) : project(n.lat, n.lon));

  function onWheel(e) {
    e.preventDefault();
    const rect = svgRef.current.getBoundingClientRect();
    const mx = vb.x + ((e.clientX - rect.left) / rect.width) * vb.w;
    const my = vb.y + ((e.clientY - rect.top) / rect.height) * vb.h;
    const k = e.deltaY > 0 ? 1.15 : 1 / 1.15;
    const w = Math.min(base0.w, Math.max(base0.w / 8, vb.w * k));
    const h = w * (base0.h / base0.w);
    setVb({ x: mx - ((mx - vb.x) / vb.w) * w, y: my - ((my - vb.y) / vb.h) * h, w, h });
  }
  function onDown(e) {
    drag.current = { x: e.clientX, y: e.clientY, vb };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  }
  function onMove(e) {
    if (!drag.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const dx = ((e.clientX - drag.current.x) / rect.width) * drag.current.vb.w;
    const dy = ((e.clientY - drag.current.y) / rect.height) * drag.current.vb.h;
    setVb({ ...drag.current.vb, x: drag.current.vb.x - dx, y: drag.current.vb.y - dy });
  }
  const onUp = () => { drag.current = null; };

  const grat = [];
  for (let lat = 10; lat <= 30; lat += 5) {
    const [x0, y] = project(lat, 110);
    const [x1] = project(lat, 148);
    grat.push(<line key={`la${lat}`} x1={x0} x2={x1} y1={y} y2={y} className="mv-grat" />);
    grat.push(<text key={`lt${lat}`} x={x0 + 0.1} y={y - 0.1} className="mv-gratlabel">{lat}°N</text>);
  }
  for (let lon = 115; lon <= 145; lon += 5) {
    const [x, y0] = project(6, lon);
    const [, y1] = project(30, lon);
    grat.push(<line key={`lo${lon}`} x1={x} x2={x} y1={y0} y2={y1} className="mv-grat" />);
    grat.push(<text key={`ln${lon}`} x={x + 0.1} y={y0 - 0.1} className="mv-gratlabel">{lon}°E</text>);
  }

  const hovered = hover ? view.facilities.find((f) => f.id === hover) : null;
  const r4 = view.facilities.filter((f) => f.role === 4);

  return (
    <div className="mv-map2d" onDoubleClick={() => setVb(base0)}>
      <svg
        ref={svgRef}
        viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
        preserveAspectRatio="xMidYMid meet"
        onWheel={onWheel}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerLeave={onUp}
      >
        <rect x={vb.x - 200} y={vb.y - 200} width={vb.w + 400} height={vb.h + 400} className="mv-sea" />
        {grat}
        <path d={landPath} className="mv-land" />

        {view.threats.map((th) => {
          const [cx, cy] = project(th.lat, th.lon);
          const on = activeThreats.has(th.id);
          return (
            <g key={th.id}>
              <circle cx={cx} cy={cy} r={th.radius_km / KM_PER_DEG} className={on ? "mv-threat on" : "mv-threat"} />
              {on && <text x={cx} y={cy - th.radius_km / KM_PER_DEG + 0.55} className="mv-threatlabel" textAnchor="middle">{th.name}</text>}
            </g>
          );
        })}

        {missions.map((m) => {
          const [x1, y1] = nodePos(m.from);
          const [x2, y2] = nodePos(m.to);
          const col = SERVICE_COLOR[m.service] || "#adb5bd";
          return (
            <line key={`l${m.id}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke={col}
              className={m.phase === 2 ? "mv-leg loaded" : "mv-leg"} />
          );
        })}

        {view.facilities.filter((f) => f.role < 4).map((f) => {
          const [x, y] = facPos(f);
          const counts = state.facCounts[f.id] || [0, 0, 0, 0];
          const n = counts.reduce((a, b) => a + b, 0);
          const col = SERVICE_COLOR[f.service] || "#adb5bd";
          const isClosed = closed.has(f.id);
          const s = f.role === 1 ? 0.16 : f.role === 2 ? 0.27 : 0.34;
          return (
            <g key={f.id} onMouseEnter={() => setHover(f.id)} onMouseLeave={() => setHover(null)} className="mv-fac">
              {f.role === 1 && <circle cx={x} cy={y} r={s} fill={col} stroke="#fff" strokeWidth="1" vectorEffect="non-scaling-stroke" />}
              {f.role === 2 && <polygon points={`${x},${y - s} ${x + s},${y} ${x},${y + s} ${x - s},${y}`} fill={col} stroke="#fff" strokeWidth="1" vectorEffect="non-scaling-stroke" />}
              {f.role === 3 && <rect x={x - s} y={y - s} width={2 * s} height={2 * s} fill={col} stroke="#fff" strokeWidth="1" vectorEffect="non-scaling-stroke" />}
              {isClosed && <circle cx={x} cy={y} r={s + 0.2} className="mv-closed" />}
              {f.role >= 2 && <text x={x} y={y + s + 0.42} className="mv-faclabel" textAnchor="middle">{f.name.replace(/^R\d /, "")}{isClosed ? " (CLOSED)" : ""}</text>}
              {n > 0 && (
                <g>
                  <circle cx={x + 0.34} cy={y - 0.34} r={0.2} fill="#0a0f16" stroke={worstColor(counts)} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
                  <text x={x + 0.34} y={y - 0.28} className="mv-badge" textAnchor="middle">{n}</text>
                </g>
              )}
            </g>
          );
        })}

        {state.recentDeaths.map((d, i) => {
          const f = model.fac[d.f];
          if (!f) return null;
          const [x, y] = facPos(f);
          return <circle key={i} cx={x} cy={y} r={0.3 + d.age * 0.35} fill="none" stroke="#fa5252" opacity={Math.max(0, 1 - d.age / 3)} strokeWidth="2" vectorEffect="non-scaling-stroke" />;
        })}

        {missions.map((m) => {
          const [fx, fy] = nodePos(m.from);
          const [tx, ty] = nodePos(m.to);
          const [x, y] = project(m.lat, m.lon);
          const ang = Math.atan2(ty - fy, tx - fx);
          const sz = VEHICLE_SIZE[m.mode] || 0.3;
          const col = SERVICE_COLOR[m.service] || "#adb5bd";
          if (m.lost) {
            const d = sz * 0.9;
            return (
              <g key={`v${m.id}`} className="mv-lost">
                <line x1={x - d} y1={y - d} x2={x + d} y2={y + d} /><line x1={x - d} y1={y + d} x2={x + d} y2={y - d} />
                <text x={x + 0.3} y={y - 0.3} className="mv-badge" fill="#fa5252">{m.asset}</text>
              </g>
            );
          }
          const pts = m.mode === "SURFACE"
            ? null
            : [[sz, 0], [-sz * 0.7, sz * 0.55], [-sz * 0.7, -sz * 0.55]]
                .map(([px, py]) => `${x + px * Math.cos(ang) - py * Math.sin(ang)},${y + px * Math.sin(ang) + py * Math.cos(ang)}`).join(" ");
          return (
            <g key={`v${m.id}`}>
              {m.nLoaded > 0 && <circle cx={x} cy={y} r={sz * 1.25} className="mv-loadring" />}
              {pts ? <polygon points={pts} fill={col} stroke="#fff" strokeWidth="1" vectorEffect="non-scaling-stroke" />
                   : <rect x={x - sz} y={y - sz * 0.3} width={sz * 2} height={sz * 0.6} fill={col} stroke="#fff" strokeWidth="1" vectorEffect="non-scaling-stroke" />}
              {m.nLoaded > 0 && <text x={x + sz * 1.3} y={y - sz * 0.9} className="mv-badge">{m.nLoaded}</text>}
            </g>
          );
        })}
      </svg>

      <div className="mv-r4box">
        <div className="mv-r4title">ROLE 4 &rarr; (off map)</div>
        {r4.map((f) => (
          <div key={f.id} className="mv-r4row">
            <span>{f.name.replace(/^R4 /, "")}</span>
            <b>{state.r4[f.id] || 0}</b>
          </div>
        ))}
      </div>

      <div className="mv-legend">
        <div>
          {ACUITY_ORDER.map((a) => (
            <span key={a}><i style={{ background: ACUITY_COLOR[a] }} />{ACUITY_LABEL[a]}</span>
          ))}
        </div>
        <div>
          {["ARMY", "NAVY", "USMC", "USAF"].map((s) => (
            <span key={s}><i style={{ background: SERVICE_COLOR[s] }} />{s}</span>
          ))}
        </div>
        <div className="mv-legend-shapes">&#9679; Role 1 &nbsp; &#9670; Role 2 &nbsp; &#9632; Role 3 &nbsp; &#9650; air &nbsp; ▬ ship &nbsp; ✕ lost</div>
      </div>

      {hovered && (
        <div className="mv-tooltip">
          <b>{hovered.name}</b>
          <div>{hovered.system_type || `Role ${hovered.role}`} · {hovered.service}</div>
          <div>beds {hovered.beds >= 999 ? "—" : hovered.beds} · OR tables {hovered.or_tables}</div>
          {(() => {
            const c = state.facCounts[hovered.id] || [0, 0, 0, 0];
            return <div>present: {ACUITY_ORDER.map((a, i) => `${c[i]} ${a.replace("IMM_", "imm ").toLowerCase()}`).join(" · ")}</div>;
          })()}
          {closed.has(hovered.id) && <div className="mv-bad">CLOSED now</div>}
        </div>
      )}
    </div>
  );
}
