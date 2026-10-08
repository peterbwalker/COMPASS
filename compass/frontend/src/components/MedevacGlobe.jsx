import { useEffect, useRef, useState } from "react";
import { loadMaps } from "../medevac/mapsLoader.js";
import { SERVICE_COLOR } from "../medevac/proj.js";

const R_EARTH_KM = 6371;
const norm = (lon) => ((((lon + 180) % 360) + 360) % 360) - 180;

function ringCoords(lat, lon, km, n = 72) {
  const d = km / R_EARTH_KM, la = (lat * Math.PI) / 180, lo = (lon * Math.PI) / 180;
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const b = (2 * Math.PI * i) / n;
    const la2 = Math.asin(Math.sin(la) * Math.cos(d) + Math.cos(la) * Math.sin(d) * Math.cos(b));
    const lo2 = lo + Math.atan2(Math.sin(b) * Math.sin(d) * Math.cos(la), Math.cos(d) - Math.sin(la) * Math.sin(la2));
    pts.push({ lat: (la2 * 180) / Math.PI, lng: norm((lo2 * 180) / Math.PI), altitude: 0 });
  }
  return pts;
}

const clear = (ref) => { for (const el of ref.current) el.remove(); ref.current = []; };

/**
 * Photorealistic 3D globe layer for the MEDEVAC replay (Map3DElement, alpha
 * channel -- same API Globe3D uses). Static layer (sites, threat rings) only
 * rebuilds when the active threat/closure set changes; the dynamic layer
 * (aircraft, ships, legs) rebuilds with the quantised clock `t`.
 */
export default function MedevacGlobe({ apiKey, model, t, onFail }) {
  const host = useRef(null);
  const mapRef = useRef(null);
  const libRef = useRef(null);
  const staticEls = useRef([]);
  const dynEls = useRef([]);
  const [ready, setReady] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await loadMaps(apiKey);
        const lib = await window.google.maps.importLibrary("maps3d");
        if (cancelled) return;
        const map = new lib.Map3DElement({
          center: { lat: 19, lng: 127, altitude: 0 },
          range: 3400000,
          tilt: 40,
          mode: lib.MapMode.HYBRID,
        });
        host.current.innerHTML = "";
        host.current.append(map);
        mapRef.current = map;
        libRef.current = lib;
        setReady(true);
      } catch (e) {
        if (!cancelled) { setErr(e.message || String(e)); onFail && setTimeout(onFail, 4000); }
      }
    })();
    return () => { cancelled = true; clear(staticEls); clear(dynEls); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiKey]);

  const threatKey = model.threatsActive(t).join(",");
  const closedKey = model.closedAt(t).join(",");

  useEffect(() => {
    if (!ready) return;
    const { Marker3DElement, Polyline3DElement, AltitudeMode } = libRef.current;
    clear(staticEls);
    const closed = new Set(closedKey ? closedKey.split(",") : []);
    for (const f of model.view.facilities) {
      if (f.role >= 4) continue;
      const m = new Marker3DElement({
        position: { lat: f.lat, lng: f.lon, altitude: 0 },
        label: `R${f.role}${f.role > 1 ? " " + f.name.replace(/^R\d /, "") : ""}${closed.has(f.id) ? " CLOSED" : ""}`,
      });
      mapRef.current.append(m);
      staticEls.current.push(m);
    }
    const active = new Set(threatKey ? threatKey.split(",") : []);
    for (const th of model.view.threats) {
      const on = active.has(th.id);
      const line = new Polyline3DElement({
        coordinates: ringCoords(th.lat, th.lon, th.radius_km),
        strokeColor: on ? "#fa5252" : "#5c6773",
        strokeWidth: on ? 5 : 1,
        altitudeMode: AltitudeMode.CLAMP_TO_GROUND,
      });
      mapRef.current.append(line);
      staticEls.current.push(line);
    }
  }, [ready, model, threatKey, closedKey]);

  useEffect(() => {
    if (!ready) return;
    const { Marker3DElement, Polyline3DElement, AltitudeMode } = libRef.current;
    clear(dynEls);
    for (const m of model.missionsAt(t)) {
      const col = SERVICE_COLOR[m.service] || "#adb5bd";
      const line = new Polyline3DElement({
        coordinates: [
          { lat: m.from.lat, lng: norm(m.from.lon), altitude: 4000 },
          { lat: m.to.lat, lng: norm(m.to.lon), altitude: 4000 },
        ],
        strokeColor: col,
        strokeWidth: m.phase === 2 ? 5 : 2,
        altitudeMode: AltitudeMode.RELATIVE_TO_GROUND,
      });
      const v = new Marker3DElement({
        position: { lat: m.lat, lng: norm(m.lon), altitude: 4000 },
        altitudeMode: AltitudeMode.RELATIVE_TO_GROUND,
        label: m.lost ? `✕ ${m.asset} lost` : `${m.asset}${m.nLoaded ? ` (${m.nLoaded})` : ""}`,
      });
      mapRef.current.append(line, v);
      dynEls.current.push(line, v);
    }
  }, [ready, model, t]);

  return (
    <div className="mv-globe">
      <div ref={host} style={{ width: "100%", height: "100%" }} />
      {!ready && !err && <div className="mv-center">Loading 3D globe…</div>}
      {err && <div className="mv-center mv-bad">3D globe unavailable: {err}<br />Returning to the tactical map…</div>}
    </div>
  );
}
