// Checkpoint map (#23): Leaflet + OpenStreetMap, fed by GET /api/stations.
"use strict";

(function () {
  const REFRESH_MS = 60 * 1000;
  // Doña Casilda Iturrizar park, Bilbao. Used until the stations are loaded.
  const DEFAULT_CENTER = [43.2662, -2.9405];
  const COLORS = { good: "#2e7d32", fair: "#f9a825", poor: "#c62828" };
  const NO_DATA_COLOR = "#9e9e9e";
  const LABELS = { good: "Good", fair: "Fair", poor: "Poor", fault: "Sensor fault" };

  const map = L.map("map").setView(DEFAULT_CENTER, 16);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);

  const markers = L.layerGroup().addTo(map);
  const status = document.getElementById("map-status");
  let fitted = false;

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[c]);
  }

  function colorFor(latest) {
    return (latest && COLORS[latest.condition]) || NO_DATA_COLOR;
  }

  function ago(timestamp, now) {
    const minutes = Math.floor((now - new Date(timestamp)) / 60000);
    if (minutes < 1) return "just now";
    if (minutes < 60) return minutes + " min ago";
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return hours + " h ago";
    return Math.floor(hours / 24) + " d ago";
  }

  function value(number, unit) {
    return number === null || number === undefined ? "–" : number + unit;
  }

  function popupHtml(station, now) {
    const latest = station.latest;
    let html = "<h3>" + escapeHtml(station.name) + "</h3>";
    if (station.description) html += "<small>" + escapeHtml(station.description) + "</small>";
    if (!latest) return html + "<p>No data yet.</p>";
    html += "<p><strong>" + (LABELS[latest.condition] || "No rating") + "</strong> for a walk</p>";
    html += "<dl>" +
      "<dt>Temperature</dt><dd>" + value(latest.temperature, " °C") + "</dd>" +
      "<dt>Humidity</dt><dd>" + value(latest.humidity, " %") + "</dd>" +
      "<dt>Light</dt><dd>" + value(latest.light, "") + "</dd>" +
      "</dl>";
    return html + "<small>Updated " + ago(latest.timestamp, now) + "</small>";
  }

  async function refresh() {
    try {
      const response = await fetch("/api/stations", { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const stations = await response.json();
      const now = new Date();

      markers.clearLayers();
      for (const station of stations) {
        L.circleMarker([station.lat, station.lon], {
          radius: 12,
          color: "#ffffff",
          weight: 3,
          fillColor: colorFor(station.latest),
          fillOpacity: 0.95,
        })
          .bindPopup(popupHtml(station, now))
          .bindTooltip(escapeHtml(station.name))
          .addTo(markers);
      }

      if (!fitted && stations.length > 0) {
        map.fitBounds(stations.map((s) => [s.lat, s.lon]), { padding: [40, 40], maxZoom: 17 });
        fitted = true;
      }
      status.textContent = "Updated at " + now.toLocaleTimeString() + ". Refreshes every minute.";
    } catch (error) {
      status.textContent = "Could not load the checkpoints. Retrying in a minute.";
    }
  }

  refresh();
  setInterval(refresh, REFRESH_MS);
})();
