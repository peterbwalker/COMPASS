import { useEffect, useRef } from "react";

const STATUS_COLOR = {
  open: "#4a9b6e",
  closed: "#c1443c",
};
const CONTESTED_COLOR = "#d98e2b";

const NODE_LABELS = {
  port: "P",
  depot: "D",
  forward_staging_area: "F",
};

/**
 * Renders nodes and routes on a Google Photorealistic 3D Map
 * (google.maps.maps3d, "alpha" channel of the Maps JavaScript API).
 * This is the current, supported replacement for the old (deprecated
 * since 2014) standalone Google Earth Plugin/API -- there is no
 * embeddable "Google Earth" product anymore, but this achieves the same
 * practical outcome: a live 3D globe with custom overlays in a web page.
 *
 * Props:
 *   apiKey: string -- Google Maps Platform API key with the Maps
 *     JavaScript API enabled and billing configured.
 *   nodes: static node list (from GET /api/scenario), each with lat/lon.
 *   routes: current-step route list (from POST /api/step), each with
 *     from/to node ids, status ("open"/"closed"), and threat_spike.
 *   highlightedRouteIds: route ids to visually emphasize (e.g. routes
 *     affected by the currently-selected COA).
 */
export default function Globe3D({ apiKey, nodes, routes, highlightedRouteIds = [] }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const overlaysRef = useRef([]); // markers + polylines currently on the map

  // One-time map creation once we have an API key.
  useEffect(() => {
    if (!apiKey || mapRef.current || !nodes || nodes.length === 0) return;

    let cancelled = false;

    (async () => {
      if (!window.google || !window.google.maps) {
        await loadMapsScript(apiKey);
      }
      if (cancelled) return;

      const { Map3DElement, MapMode } = await google.maps.importLibrary("maps3d");

      const centerLat = average(nodes.map((n) => n.lat));
      const centerLon = average(nodes.map((n) => n.lon));

      const map = new Map3DElement({
        center: { lat: centerLat, lng: centerLon, altitude: 0 },
        range: 900000, // meters -- wide enough to see the whole scenario area
        tilt: 55,
        mode: MapMode.HYBRID,
      });

      containerRef.current.innerHTML = "";
      containerRef.current.append(map);
      mapRef.current = map;
    })();

    return () => {
      cancelled = true;
    };
  }, [apiKey, nodes]);

  // Redraw overlays whenever routes/highlighting change.
  useEffect(() => {
    if (!mapRef.current || !nodes || !routes) return;

    (async () => {
      const { Marker3DElement, Polyline3DElement, AltitudeMode } =
        await google.maps.importLibrary("maps3d");

      // Clear previous overlays before redrawing.
      for (const el of overlaysRef.current) el.remove();
      overlaysRef.current = [];

      const nodeById = Object.fromEntries(nodes.map((n) => [n.id, n]));

      for (const node of nodes) {
        const marker = new Marker3DElement({
          position: { lat: node.lat, lng: node.lon, altitude: 0 },
          label: NODE_LABELS[node.type] || node.id[0],
        });
        mapRef.current.append(marker);
        overlaysRef.current.push(marker);
      }

      for (const route of routes) {
        const from = nodeById[route.from];
        const to = nodeById[route.to];
        if (!from || !to) continue;

        const isHighlighted = highlightedRouteIds.includes(route.id);
        const color = route.threat_spike
          ? CONTESTED_COLOR
          : STATUS_COLOR[route.status] || STATUS_COLOR.open;

        const line = new Polyline3DElement({
          coordinates: [
            { lat: from.lat, lng: from.lon, altitude: 0 },
            { lat: to.lat, lng: to.lon, altitude: 0 },
          ],
          strokeColor: color,
          strokeWidth: isHighlighted ? 6 : 3,
          altitudeMode: AltitudeMode.CLAMP_TO_GROUND,
        });
        mapRef.current.append(line);
        overlaysRef.current.push(line);
      }
    })();
  }, [nodes, routes, highlightedRouteIds]);

  if (!apiKey) return null;

  return <div ref={containerRef} style={{ width: "100%", height: "100%" }} />;
}

function average(values) {
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function loadMapsScript(apiKey) {
  return new Promise((resolve, reject) => {
    if (document.getElementById("google-maps-script")) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.id = "google-maps-script";
    script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&v=alpha`;
    script.async = true;
    script.onload = resolve;
    script.onerror = reject;
    document.head.append(script);
  });
}
