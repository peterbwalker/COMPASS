// Loads the Google Maps JS API (alpha channel, needed for Map3DElement) exactly
// once, and waits until importLibrary actually exists. Safe if another
// component (Globe3D) already added the same <script> but it is still loading.
let pending = null;

export function loadMaps(apiKey) {
  if (window.google && window.google.maps && window.google.maps.importLibrary) return Promise.resolve();
  if (pending) return pending;
  pending = new Promise((resolve, reject) => {
    const waitReady = () => {
      const t0 = Date.now();
      (function poll() {
        if (window.google && window.google.maps && window.google.maps.importLibrary) resolve();
        else if (Date.now() - t0 > 15000) reject(new Error("Google Maps API did not initialise (check the key and that billing / Maps JavaScript API are enabled)"));
        else setTimeout(poll, 50);
      })();
    };
    if (document.getElementById("google-maps-script")) {
      waitReady();
      return;
    }
    const s = document.createElement("script");
    s.id = "google-maps-script";
    s.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&v=alpha`;
    s.async = true;
    s.onload = waitReady;
    s.onerror = () => reject(new Error("Could not load the Google Maps script"));
    document.head.append(s);
  });
  pending.catch(() => { pending = null; });
  return pending;
}
