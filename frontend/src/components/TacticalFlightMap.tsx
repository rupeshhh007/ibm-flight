import { useEffect, useRef, useState } from "react";
import type { AircraftTelemetry } from "../api/types";
import { computeFlightRoutePosition, FLIGHT_WAYPOINTS } from "../api/weather";
import { useAeroWeather } from "../hooks/useAeroWeather";
import { formatNumber } from "./format";
import "leaflet/dist/leaflet.css";

interface TacticalFlightMapProps {
  telemetry: AircraftTelemetry | null | undefined;
  trackHistory?: AircraftTelemetry[];
  isIncident?: boolean;
  incidentLabel?: string;
  runEventsCount?: number;
}

const TILE_LAYERS = {
  satellite: {
    name: "TrueColor Satellite",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: "&copy; Esri &mdash; Earthstar Geographics",
    maxZoom: 18,
  },
  street: {
    name: "Daylight Navigation",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19,
  },
  terrain: {
    name: "World Topography",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
    attribution: "&copy; Esri &mdash; USGS, NOAA",
    maxZoom: 18,
  },
};

type LayerType = keyof typeof TILE_LAYERS;

export function TacticalFlightMap({
  telemetry,
  trackHistory = [],
  isIncident = false,
  incidentLabel = "Loss of Response",
  runEventsCount = 0,
}: TacticalFlightMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapInstanceRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const aircraftMarkerRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const incidentLayerRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const currentTileLayerRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const radarLayerRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const trackPolylineRef = useRef<any>(null);

  const [activeLayer, setActiveLayer] = useState<LayerType>("satellite");
  const [selectedWaypointId, setSelectedWaypointId] = useState<string>("AUTO");
  const [showRadar, setShowRadar] = useState(false);
  const [showWeatherBriefing, setShowWeatherBriefing] = useState(false);
  const [mapLoaded, setMapLoaded] = useState(false);

  // Compute flight position synchronized with scenario progression
  const progressRatio = Math.min(1, runEventsCount / 18);
  const routePos = computeFlightRoutePosition(progressRatio);

  let currentLat = telemetry?.latitude ?? 19.0760;
  let currentLon = telemetry?.longitude ?? 72.8777;
  let currentHeading = telemetry?.heading_deg ?? 90;

  if (selectedWaypointId === "WP1") {
    currentLat = 19.0760;
    currentLon = 72.8777;
    currentHeading = 120;
  } else if (selectedWaypointId === "WP2") {
    currentLat = 18.5204;
    currentLon = 73.8567;
    currentHeading = 102;
  } else if (selectedWaypointId === "WP3") {
    currentLat = 17.3850;
    currentLon = 78.4867;
    currentHeading = 102;
  } else {
    // AUTO flight progression
    if (telemetry?.latitude !== undefined && telemetry.latitude !== 19.0760) {
      currentLat = telemetry.latitude;
      currentLon = telemetry.longitude;
      currentHeading = telemetry.heading_deg ?? 90;
    } else {
      currentLat = routePos.latitude;
      currentLon = routePos.longitude;
      currentHeading = routePos.heading;
    }
  }

  const altitudeFt = telemetry?.altitude_ft ?? 35000;
  const iasKts = telemetry?.airspeed_kts ?? 450;

  // Live Meteorological Atmosphere & Doppler Radar for exact flight location
  const { weather, radarTileUrl } = useAeroWeather({
    latitude: currentLat,
    longitude: currentLon,
    altitudeFt,
  });

  const handleSelectWaypoint = (wpId: string) => {
    setSelectedWaypointId(wpId);
    let targetLat = currentLat;
    let targetLon = currentLon;
    if (wpId === "WP1") {
      targetLat = 19.0760;
      targetLon = 72.8777;
    } else if (wpId === "WP2") {
      targetLat = 18.5204;
      targetLon = 73.8567;
    } else if (wpId === "WP3") {
      targetLat = 17.3850;
      targetLon = 78.4867;
    } else {
      targetLat = routePos.latitude;
      targetLon = routePos.longitude;
    }
    if (mapInstanceRef.current) {
      mapInstanceRef.current.panTo([targetLat, targetLon], { animate: true });
    }
  };

  const handleSelectWaypointRef = useRef(handleSelectWaypoint);
  handleSelectWaypointRef.current = handleSelectWaypoint;

  // Sync Live Radar Overlay with Leaflet Map
  useEffect(() => {
    if (!mapInstanceRef.current) return;

    import("leaflet").then((L) => {
      if (showRadar && radarTileUrl) {
        if (!radarLayerRef.current) {
          radarLayerRef.current = L.tileLayer(radarTileUrl, {
            opacity: 0.65,
            zIndex: 400,
          }).addTo(mapInstanceRef.current);
        }
      } else {
        if (radarLayerRef.current && mapInstanceRef.current) {
          mapInstanceRef.current.removeLayer(radarLayerRef.current);
          radarLayerRef.current = null;
        }
      }
    }).catch(() => undefined);
  }, [showRadar, radarTileUrl]);

  // Initialize Leaflet Map
  useEffect(() => {
    let isCancelled = false;

    async function initMap() {
      if (!mapContainerRef.current) return;
      if (typeof window === "undefined") return;

      try {
        const L = await import("leaflet");

        if (isCancelled || !mapContainerRef.current) return;

        // Clean up previous instance if any
        if (mapInstanceRef.current) {
          mapInstanceRef.current.remove();
          mapInstanceRef.current = null;
        }

        const map = L.map(mapContainerRef.current, {
          center: [currentLat, currentLon],
          zoom: 7,
          zoomControl: false,
          attributionControl: false,
        });

        // Add Base Tile Layer (Satellite by default)
        const tileConfig = TILE_LAYERS[activeLayer];
        const tileLayer = L.tileLayer(tileConfig.url, {
          attribution: tileConfig.attribution,
          maxZoom: tileConfig.maxZoom,
        }).addTo(map);

        currentTileLayerRef.current = tileLayer;

        // Custom Zoom Control at bottom right
        L.control.zoom({ position: "bottomright" }).addTo(map);

        // Draw Waypoint Route Polyline
        const routePoints = FLIGHT_WAYPOINTS.map((w) => [w.lat, w.lon] as [number, number]);
        L.polyline(routePoints, {
          color: "#38bdf8",
          weight: 2.5,
          dashArray: "6, 6",
          opacity: 0.8,
        }).addTo(map);

        // Add Interactive Waypoint Markers
        FLIGHT_WAYPOINTS.forEach((wp) => {
          const wpIcon = L.divIcon({
            className: "waypoint-marker-icon",
            html: `
              <div class="leaflet-wp-node" style="cursor: pointer;">
                <span class="wp-ping"></span>
                <span class="wp-label">${wp.id}</span>
                <span class="wp-time">${wp.time}</span>
              </div>
            `,
            iconSize: [40, 40],
            iconAnchor: [20, 20],
          });
          const marker = L.marker([wp.lat, wp.lon], { icon: wpIcon }).addTo(map);
          marker.bindTooltip(
            `<strong>${wp.id}: ${wp.name}</strong><br/>Station: ${wp.stationId}<br/>Click to synchronize weather`,
            { direction: "top", offset: [0, -10] }
          );
          marker.on("click", () => {
            handleSelectWaypointRef.current(wp.id);
          });
        });

        // Aircraft Marker SVG Icon
        const createAircraftIcon = (heading: number) =>
          L.divIcon({
            className: "aircraft-marker-container",
            html: `
              <div class="aircraft-glow-wrapper" style="transform: rotate(${heading}deg);">
                <div class="aircraft-ping"></div>
                <svg viewBox="0 0 48 48" class="aircraft-marker-svg" width="38" height="38">
                  <path
                    d="M24 4 C25 6, 26 14, 26 23 L42 27 L42 32 L26 27 L25 40 L31 43 L31 46 L24 44 L17 46 L17 43 L23 40 L22 27 L6 32 L6 27 L22 23 C22 14, 23 6, 24 4 Z"
                    fill="#ffffff"
                    stroke="#0284c7"
                    stroke-width="1.5"
                  />
                  <circle cx="24" cy="24" r="3" fill="#38bdf8" />
                </svg>
              </div>
            `,
            iconSize: [48, 48],
            iconAnchor: [24, 24],
          });

        const planeMarker = L.marker([currentLat, currentLon], {
          icon: createAircraftIcon(currentHeading),
          zIndexOffset: 1000,
        }).addTo(map);

        planeMarker.bindTooltip(
          `<strong>SIM-001 (B737)</strong><br/>ALT: ${formatNumber(altitudeFt)} FT<br/>IAS: ${Math.round(iasKts)} KT<br/>HDG: ${Math.round(currentHeading)}°`,
          { permanent: false, direction: "top", offset: [0, -18], className: "aircraft-tooltip" }
        );

        aircraftMarkerRef.current = planeMarker;

        // Incident Zone Radar Circle & Beacon (if active)
        if (isIncident) {
          const incidentCenter: [number, number] = [18.5204, 73.8567]; // WP2 Zone
          const incidentCircle = L.circle(incidentCenter, {
            color: "#ef4444",
            fillColor: "#ef4444",
            fillOpacity: 0.18,
            weight: 2,
            dashArray: "4, 4",
            radius: 35000, // 35 km
          }).addTo(map);

          const beaconIcon = L.divIcon({
            className: "incident-beacon-container",
            html: `
              <div class="incident-beacon-node">
                <span class="beacon-pulse-outer"></span>
                <span class="beacon-pulse-inner"></span>
                <span class="beacon-icon">⚠</span>
                <span class="beacon-label">INCIDENT ZONE</span>
                <span class="beacon-sub">${incidentLabel}</span>
              </div>
            `,
            iconSize: [60, 60],
            iconAnchor: [30, 30],
          });

          const beaconMarker = L.marker(incidentCenter, { icon: beaconIcon }).addTo(map);
          incidentLayerRef.current = L.layerGroup([incidentCircle, beaconMarker]).addTo(map);
        }

        mapInstanceRef.current = map;
        setMapLoaded(true);
      } catch {
        // Fallback silently if environment cannot initialize Leaflet (e.g. headless jsdom)
        setMapLoaded(false);
      }
    }

    void initMap();

    return () => {
      isCancelled = true;
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []); // Run on mount

  // Update Aircraft Position & Heading Dynamically
  useEffect(() => {
    if (!mapInstanceRef.current || !aircraftMarkerRef.current) return;

    import("leaflet").then((L) => {
      const plane = aircraftMarkerRef.current;
      if (plane) {
        plane.setLatLng([currentLat, currentLon]);

        const wrapper = plane.getElement()?.querySelector(".aircraft-glow-wrapper") as HTMLElement | null;
        if (wrapper) {
          wrapper.style.transform = `rotate(${currentHeading}deg)`;
        }

        plane.setTooltipContent(
          `<strong>SIM-001 (B737)</strong><br/>ALT: ${formatNumber(altitudeFt)} FT<br/>IAS: ${Math.round(iasKts)} KT<br/>HDG: ${Math.round(currentHeading)}°<br/>STATION: ${weather.stationId}`
        );
      }

      // Update Track Polyline
      if (trackHistory.length > 1) {
        const points = trackHistory.map((t) => [t.latitude, t.longitude] as [number, number]);
        if (trackPolylineRef.current) {
          trackPolylineRef.current.setLatLngs(points);
        } else {
          trackPolylineRef.current = L.polyline(points, {
            color: "#10b981",
            weight: 2,
            opacity: 0.9,
          }).addTo(mapInstanceRef.current);
        }
      }
    }).catch(() => undefined);
  }, [currentLat, currentLon, currentHeading, altitudeFt, iasKts, trackHistory, weather.stationId]);

  // Handle Tile Layer Switching
  const handleSwitchLayer = async (layerKey: LayerType) => {
    setActiveLayer(layerKey);
    if (!mapInstanceRef.current) return;

    try {
      const L = await import("leaflet");
      if (currentTileLayerRef.current) {
        mapInstanceRef.current.removeLayer(currentTileLayerRef.current);
      }
      const tileConfig = TILE_LAYERS[layerKey];
      const newLayer = L.tileLayer(tileConfig.url, {
        attribution: tileConfig.attribution,
        maxZoom: tileConfig.maxZoom,
      }).addTo(mapInstanceRef.current);

      currentTileLayerRef.current = newLayer;
    } catch {
      // Ignored
    }
  };

  // Recenter Map on Aircraft
  const handleRecenter = () => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.panTo([currentLat, currentLon], { animate: true });
    }
  };

  return (
    <div className="tactical-flight-map-root">
      {/* Real Interactive Leaflet Container */}
      <div ref={mapContainerRef} className="leaflet-map-canvas" />

      {/* Top Left Weather & Flight Data HUD */}
      <div className="map-hud-overlay map-hud-top-left">
        <div
          className="tactical-weather-widget"
          onClick={() => setShowWeatherBriefing(!showWeatherBriefing)}
          title="Click to view Live Meteorological Briefing & METAR (Open-Meteo API)"
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") setShowWeatherBriefing(!showWeatherBriefing);
          }}
        >
          <div className="weather-title">
            <span className="weather-live-dot" />
            <span>WEATHER & SATELLITE ATMOSPHERE</span>
            <span className="weather-toggle-indicator">{showWeatherBriefing ? "▲ Hide" : "▼ METAR"}</span>
          </div>
          <div className="weather-stats">
            <span>{weather.icon} {weather.condition}</span>
            <span>{weather.temperatureAloftC}°C</span>
            <span>{weather.windSpeedKt} KT @ {weather.windDirectionDeg}°</span>
            <span className="text-highlight">{weather.flightLevel}</span>
          </div>
        </div>

        {/* Expandable Aviation Weather Briefing & METAR Modal */}
        {showWeatherBriefing && (
          <div className="weather-briefing-card" role="dialog" aria-label="Aviation Weather Briefing">
            <div className="weather-briefing-header">
              <div className="briefing-title-row">
                <span className="station-code">{weather.stationId}</span>
                <span className="station-name">{weather.stationName}</span>
                <span className="live-pill">{weather.isLive ? "LIVE OPEN-METEO" : "SIMULATION ISA"}</span>
              </div>
              <button
                type="button"
                className="close-briefing-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowWeatherBriefing(false);
                }}
              >
                ✕
              </button>
            </div>

            <div className="weather-grid-details">
              <div className="briefing-stat-box">
                <span className="stat-label">CONDITIONS</span>
                <span className="stat-val">{weather.icon} {weather.condition}</span>
              </div>
              <div className="briefing-stat-box">
                <span className="stat-label">WINDS ALOFT</span>
                <span className="stat-val mono">{weather.windDirectionDeg}° @ {weather.windSpeedKt} KT</span>
              </div>
              <div className="briefing-stat-box">
                <span className="stat-label">SURFACE TEMP</span>
                <span className="stat-val mono">{weather.surfaceTempC}°C / {weather.surfaceTempF}°F</span>
              </div>
              <div className="briefing-stat-box">
                <span className="stat-label">TEMP AT {weather.flightLevel}</span>
                <span className="stat-val mono text-cyan">{weather.temperatureAloftC}°C</span>
              </div>
              <div className="briefing-stat-box">
                <span className="stat-label">ALTIMETER / QNH</span>
                <span className="stat-val mono">{weather.surfacePressureHpa} hPa ({weather.altimeterInHg} inHg)</span>
              </div>
              <div className="briefing-stat-box">
                <span className="stat-label">DEW POINT / RH</span>
                <span className="stat-val mono">{weather.dewPointC}°C · {weather.relativeHumidity}%</span>
              </div>
            </div>

            <div className="metar-display-section">
              <span className="metar-label">SIMULATED ICAO METAR OBSERVATION</span>
              <pre className="metar-raw-text mono">{weather.metarRaw}</pre>
            </div>

            <div className="weather-disclaimer">
              SIMULATION ONLY — METEOROLOGICAL TELEMETRY FOR SIMULATOR DEMONSTRATION
            </div>
          </div>
        )}
      </div>

      {/* Top Right Realistic Map Layer Controls */}
      <div className="map-hud-overlay map-hud-top-right">
        <div className="map-layer-selector">
          {(Object.keys(TILE_LAYERS) as LayerType[]).map((key) => (
            <button
              key={key}
              type="button"
              className={`layer-switch-btn ${activeLayer === key ? "is-active" : ""}`}
              onClick={() => handleSwitchLayer(key)}
            >
              {key === "satellite" ? "🛰️ Satellite" : key === "terrain" ? "🏔️ Topo Terrain" : "🗺️ Navigation"}
            </button>
          ))}
          <button
            type="button"
            className={`layer-switch-btn ${showRadar ? "is-active" : ""}`}
            onClick={() => setShowRadar(!showRadar)}
            title="Toggle Live Precipitation Doppler Radar (RainViewer API)"
          >
            🌧️ {showRadar ? "Radar ON" : "Radar"}
          </button>
          <button
            type="button"
            className="layer-switch-btn recenter-btn"
            onClick={handleRecenter}
            title="Recenter aircraft"
          >
            🎯 Recenter
          </button>
        </div>
      </div>

      {/* Bottom Right Route Waypoint Selector HUD */}
      <div className="map-hud-overlay map-hud-bottom-right">
        <div className="waypoint-nav-selector" role="group" aria-label="Route Waypoint Selector">
          <span className="wp-nav-title">SYNC LOCATION:</span>
          <button
            type="button"
            className={`wp-nav-btn ${selectedWaypointId === "AUTO" ? "is-active" : ""}`}
            onClick={() => handleSelectWaypoint("AUTO")}
            title="Auto-synchronize with current flight progress"
          >
            🔄 AUTO ({routePos.stationId})
          </button>
          {FLIGHT_WAYPOINTS.map((wp) => (
            <button
              key={wp.id}
              type="button"
              className={`wp-nav-btn ${selectedWaypointId === wp.id ? "is-active" : ""}`}
              onClick={() => handleSelectWaypoint(wp.id)}
              title={`Jump to ${wp.name} to inspect local weather`}
            >
              📍 {wp.id} ({wp.stationId})
            </button>
          ))}
        </div>
      </div>

      {/* Bottom Left Tactical Position HUD */}
      <div className="map-hud-overlay map-hud-bottom-left">
        <div className="tactical-telemetry-badge mono">
          <span>LAT: {currentLat.toFixed(4)}°N</span>
          <span>LON: {currentLon.toFixed(4)}°E</span>
          <span className="badge-station text-cyan">STATION: {weather.stationId} ({weather.condition} {weather.icon})</span>
          <span>AIRWAY: {routePos.legLabel}</span>
        </div>
      </div>

      {/* Fallback Display if Leaflet is loading or offline */}
      {!mapLoaded && (
        <div className="leaflet-loading-placeholder">
          <span className="spinner" />
          <span>Loading Realistic Satellite Map…</span>
        </div>
      )}
    </div>
  );
}
