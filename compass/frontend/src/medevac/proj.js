// Shared 2D projection for the tactical map. Equirectangular with a fixed
// cos(18 deg) longitude scale, so one unit == one degree of latitude and
// circles of a given km radius are true circles. landPath.js is generated in
// the same coordinates (see gen_land.mjs).
export const LON0 = 108;
export const LAT_TOP = 32;
export const K = Math.cos((18 * Math.PI) / 180);
export const KM_PER_DEG = 111.2;

export const VIEW = { lonMin: 110, lonMax: 148, latMin: 6, latMax: 30 };

// Wrap longitude into [LON0, LON0+360) so Role 4 sites east of the dateline
// (Honolulu, Pacific Northwest, San Diego) land far to the right, not far left.
export const wrapLon = (lon) => ((((lon - LON0) % 360) + 360) % 360) + LON0;

export function project(lat, lon) {
  return [(wrapLon(lon) - LON0) * K, LAT_TOP - lat];
}

export const viewBox = () => {
  const [x0, y0] = project(VIEW.latMax, VIEW.lonMin);
  const [x1, y1] = project(VIEW.latMin, VIEW.lonMax);
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
};

export const inView = (lat, lon) =>
  lat >= VIEW.latMin && lat <= VIEW.latMax && lon >= VIEW.lonMin && lon <= VIEW.lonMax;

export const ACUITY_COLOR = {
  IMM_SURG: "#fa5252",
  IMM_MED: "#ff922b",
  DELAYED: "#fcc419",
  MINIMAL: "#69db7c",
};
export const ACUITY_ORDER = ["IMM_SURG", "IMM_MED", "DELAYED", "MINIMAL"];
export const ACUITY_LABEL = {
  IMM_SURG: "Immediate, surgical",
  IMM_MED: "Immediate, medical",
  DELAYED: "Delayed",
  MINIMAL: "Minimal",
};
export const SERVICE_COLOR = {
  ARMY: "#94d82d",
  NAVY: "#4c6ef5",
  USMC: "#cc5de8",
  USAF: "#22b8cf",
  JOINT: "#adb5bd",
};
