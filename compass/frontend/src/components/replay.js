// Pure replay logic: turns one /api/medevac/simulate response (detail=true)
// into queryable state at any simulated hour. No React, no DOM -- testable in node.
import { ACUITY_ORDER } from "./proj.js";

const ACU_IDX = Object.fromEntries(ACUITY_ORDER.map((a, i) => [a, i]));
const LINGER_H = 6; // how long a loss marker stays on the map

// Interpolate along the short way around the globe (handles the dateline).
function lerp(a, b, f) {
  let dl = b.lon - a.lon;
  if (dl > 180) dl -= 360;
  if (dl < -180) dl += 360;
  return { lat: a.lat + (b.lat - a.lat) * f, lon: a.lon + dl * f };
}

function timelineOf(p, zoneById) {
  const r1 = zoneById[p.zone]?.r1_id;
  const ev = [{ t: p.t0, s: "at", f: r1, tac: true }];
  for (const [t, txt] of p.log || []) {
    let m;
    if ((m = txt.match(/^arrive (\S+)/))) ev.push({ t, s: "at", f: m[1] });
    else if ((m = txt.match(/^boarded (\S+) -> (\S+)/))) ev.push({ t, s: "transit", a: m[1], to: m[2] });
    else if ((m = txt.match(/^done @ (\S+)/))) ev.push({ t, s: "done", f: m[1] });
    else if (txt.startsWith("DIED")) ev.push({ t, s: "dead", cause: (txt.match(/\((.*)\)/) || [])[1] });
  }
  ev.sort((a, b) => a.t - b.t);
  let lastF = r1;
  for (const e of ev) {
    if (e.f) lastF = e.f;
    if (e.s === "dead") e.f = lastF;
  }
  return { id: p.id, acuity: p.acuity, aIdx: ACU_IDX[p.acuity], t0: p.t0, ev };
}

export function buildModel(sim) {
  const view = sim.scenario_view;
  const fac = Object.fromEntries(view.facilities.map((f) => [f.id, f]));
  const base = Object.fromEntries(view.bases.map((b) => [b.id, b]));
  const zoneById = Object.fromEntries(view.zones.map((z) => [z.id, z]));
  const asset = Object.fromEntries(view.assets.map((a) => [a.id, a]));
  const node = (id) => fac[id] || base[id];
  const patients = sim.patients.map((p) => timelineOf(p, zoneById));
  const missions = sim.missions;

  const lossTime = (m) => {
    if (m.outcome === "LOST_OUTBOUND") return m.t_depart + (m.t_pickup - m.t_depart) / 2;
    if (m.outcome === "LOST_LOADED") return m.t_pickup + (m.t_deliver - m.t_pickup) / 2;
    if (m.outcome === "LOST_RETURN") return m.t_deliver + (m.t_return - m.t_deliver) / 2;
    return null;
  };

  const tEnd = Math.max(
    sim.metrics?.sim_end_h || 0,
    ...missions.map((m) => m.t_return || 0),
    ...patients.map((p) => p.ev[p.ev.length - 1].t),
    24
  );

  function stateAt(t) {
    const facCounts = {};
    const transit = [0, 0, 0, 0];
    const r4 = {};
    let dead = 0, done = 0, total = 0;
    const recentDeaths = [];
    for (const p of patients) {
      if (t < p.t0) continue;
      total++;
      let cur = p.ev[0];
      for (let i = 1; i < p.ev.length && p.ev[i].t <= t; i++) cur = p.ev[i];
      if (cur.s === "at") {
        (facCounts[cur.f] ||= [0, 0, 0, 0])[p.aIdx]++;
      } else if (cur.s === "transit") {
        transit[p.aIdx]++;
      } else if (cur.s === "done") {
        done++;
        if (fac[cur.f]?.role === 4) r4[cur.f] = (r4[cur.f] || 0) + 1;
      } else if (cur.s === "dead") {
        dead++;
        if (t - cur.t < 3) recentDeaths.push({ f: cur.f, age: t - cur.t, acuity: p.acuity });
      }
    }
    const inSystem = total - dead - done;
    return { facCounts, transit, r4, dead, done, total, inSystem, recentDeaths };
  }

  function missionsAt(t) {
    const out = [];
    for (const m of missions) {
      const a = asset[m.asset];
      if (!a) continue;
      const lt = lossTime(m);
      const endT = lt !== null ? lt + LINGER_H : m.t_return;
      if (t < m.t_depart || t > endT) continue;
      const b = base[a.base_id], o = node(m.origin), d = node(m.dest);
      let from, to, f, phase;
      if (t < m.t_pickup) { phase = 1; from = b; to = o; f = (t - m.t_depart) / Math.max(1e-6, m.t_pickup - m.t_depart); }
      else if (t < m.t_deliver) { phase = 2; from = o; to = d; f = (t - m.t_pickup) / Math.max(1e-6, m.t_deliver - m.t_pickup); }
      else { phase = 3; from = d; to = b; f = (t - m.t_deliver) / Math.max(1e-6, m.t_return - m.t_deliver); }
      const lost = lt !== null && t >= lt;
      if (lost) f = 0.5;
      const pos = lerp(from, to, Math.min(1, Math.max(0, f)));
      out.push({
        id: m.id, asset: m.asset, mode: a.mode, service: a.service, phase, lost,
        lat: pos.lat, lon: pos.lon, from, to, origin: o, dest: d, base: b,
        nLoaded: phase === 2 ? (m.boarded || []).length : 0, outcome: m.outcome,
      });
    }
    return out;
  }

  const threatsActive = (t) => view.threats.filter((x) => t >= x.start_h && t <= x.end_h).map((x) => x.id);
  const closedAt = (t) => view.closures.filter((c) => t >= c.start_h && t <= c.end_h).map((c) => c.facility_id);

  const events = [];
  for (const p of patients) {
    for (const e of p.ev) if (e.s === "dead") events.push({ t: e.t, kind: "death", acuity: p.acuity, text: `${p.id} died (${(e.cause || "").toLowerCase().replace(/_/g, " ")})` });
  }
  for (const m of missions) {
    const lt = lossTime(m);
    if (lt !== null) events.push({ t: lt, kind: "loss", text: `${m.asset} lost (${m.outcome.replace("LOST_", "").toLowerCase()})` });
  }
  for (const c of view.closures) events.push({ t: c.start_h, kind: "closure", text: `${fac[c.facility_id]?.name || c.facility_id} closed` });
  for (const th of view.threats) events.push({ t: th.start_h, kind: "threat", text: `${th.name} active` });
  events.sort((a, b) => a.t - b.t);
  const eventsUpTo = (t, n = 7) => events.filter((e) => e.t <= t).slice(-n).reverse();

  const series = [];
  for (let h = 0; h <= Math.ceil(tEnd); h += 1) {
    const s = stateAt(h);
    series.push({ t: h, dead: s.dead, done: s.done, inSystem: s.inSystem });
  }

  return { view, fac, base, asset, tEnd, stateAt, missionsAt, threatsActive, closedAt, eventsUpTo, series };
}

export const clockLabel = (t) => {
  const d = Math.floor(t / 24) + 1;
  const h = Math.floor(t % 24);
  return `D${d} ${String(h).padStart(2, "0")}:00`;
};
