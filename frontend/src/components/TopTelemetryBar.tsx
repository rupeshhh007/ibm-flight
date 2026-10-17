import { useEffect, useMemo, useState } from "react";
import { formatNumber, formatVirtualTime, humanize } from "./format";
import { GUARDIAN_TONE, SENTINEL_TONE } from "./tones";
import { Pill } from "./ui";
import { computeFlightRoutePosition } from "../api/weather";
import { useAeroGuard } from "../hooks/useAeroGuard";
import { useAeroWeather } from "../hooks/useAeroWeather";
import { soundEffects } from "../utils/soundEffects";

export function TopTelemetryBar() {
  const { snapshot, events, connection, syncError } = useAeroGuard();
  const [isMuted, setIsMuted] = useState(soundEffects.getMuted());

  useEffect(() => {
    return soundEffects.onMuteChange(setIsMuted);
  }, []);

  const telemetry = snapshot?.telemetry;
  const isEmergency = Boolean(snapshot?.active_incident) || snapshot?.guardian_state === "ESCALATED";

  const runEvents = useMemo(() => {
    if (!snapshot?.scenario_run_id) return [];
    return events.filter((e) => e.scenario_run_id === snapshot.scenario_run_id);
  }, [events, snapshot?.scenario_run_id]);

  const progressRatio = Math.min(1, runEvents.length / 18);
  const routePos = computeFlightRoutePosition(progressRatio);

  const activeLat = telemetry?.latitude !== undefined && telemetry.latitude !== 19.0760
    ? telemetry.latitude
    : routePos.latitude;
  const activeLon = telemetry?.longitude !== undefined && telemetry.longitude !== 72.8777
    ? telemetry.longitude
    : routePos.longitude;
  const activeHeading = telemetry?.heading_deg !== undefined && telemetry.heading_deg !== 90
    ? telemetry.heading_deg
    : routePos.heading;

  const callsign = "SIM-001";
  const altitudeFt = telemetry?.altitude_ft ?? 35000;
  const { weather } = useAeroWeather({
    latitude: activeLat,
    longitude: activeLon,
    altitudeFt,
  });
  const flightLevel = `FL${Math.round(altitudeFt / 100)}`;
  const iasKts = `${Math.round(telemetry?.airspeed_kts ?? 450)} KT`;
  const headingDeg = `${String(Math.round(activeHeading)).padStart(3, "0")}°`;
  const altitudeStr = `${formatNumber(altitudeFt)} FT`;
  const simTimeStr = snapshot?.virtual_time ? formatVirtualTime(snapshot.virtual_time) : "00:07:32";

  const connectionTone = connection === "online" ? (syncError ? "warn" : "ok") : connection === "offline" ? "alert" : "muted";

  return (
    <header className="telemetry-topbar">
      <div className="telemetry-strip">
        <div className="telemetry-cell">
          <span className="telemetry-cell__label">CALLSIGN</span>
          <span className="telemetry-cell__value mono text-highlight">{callsign}</span>
        </div>

        <div className="telemetry-cell">
          <span className="telemetry-cell__label">FLIGHT LEVEL</span>
          <span className="telemetry-cell__value mono">{flightLevel}</span>
        </div>

        <div className="telemetry-cell">
          <span className="telemetry-cell__label">IAS</span>
          <span className="telemetry-cell__value mono">{iasKts}</span>
        </div>

        <div className="telemetry-cell">
          <span className="telemetry-cell__label">HEADING</span>
          <span className="telemetry-cell__value mono">{headingDeg}</span>
        </div>

        <div className="telemetry-cell">
          <span className="telemetry-cell__label">ALTITUDE</span>
          <span className="telemetry-cell__value mono">{altitudeStr}</span>
        </div>

        <div className="telemetry-cell">
          <span className="telemetry-cell__label">SIM TIME</span>
          <span className="telemetry-cell__value mono text-cyan">{simTimeStr}</span>
        </div>

        <div
          className="telemetry-cell telemetry-cell--weather"
          title={`${weather.stationName} | Location: ${activeLat.toFixed(4)}°N, ${activeLon.toFixed(4)}°E | Surface: ${weather.surfaceTempC}°C | Aloft: ${weather.temperatureAloftC}°C | Winds: ${weather.windDirectionDeg}° @ ${weather.windSpeedKt} KT | QNH ${weather.surfacePressureHpa} hPa`}
        >
          <span className="telemetry-cell__label">
            WEATHER {weather.isLive ? <span className="weather-live-indicator">LIVE</span> : ""} <span className="text-cyan">({weather.stationId})</span>
          </span>
          <span className="telemetry-cell__subtext">
            <span>{weather.icon} {weather.condition}</span>
            <span>{weather.temperatureAloftC}°C</span>
            <span>{weather.windSpeedKt} KT</span>
          </span>
        </div>
      </div>

      <div className="topbar__status" aria-label="System status">
        <Pill tone={connectionTone} pulse={connection === "connecting"}>
          Backend {connection === "online" ? (syncError ? "degraded" : "online") : connection}
        </Pill>
        {snapshot && (
          <>
            <Pill tone={GUARDIAN_TONE[snapshot.guardian_state]}>Guardian {humanize(snapshot.guardian_state)}</Pill>
            <Pill tone={SENTINEL_TONE[snapshot.sentinel_state]}>Sentinel {humanize(snapshot.sentinel_state)}</Pill>
          </>
        )}

        {/* Interactive Audio Toggle Button */}
        <button
          type="button"
          className={`icon-btn audio-toggle-btn ${isMuted ? "is-muted" : "is-active"}`}
          title={isMuted ? "Avionics Audio Muted (Click to enable sound)" : "Avionics Sound Active (Click to mute)"}
          aria-label={isMuted ? "Unmute audio alerts" : "Mute audio alerts"}
          onClick={() => {
            const nextMuted = soundEffects.toggleMute();
            if (!nextMuted) {
              soundEffects.playAckChime();
            }
          }}
        >
          {isMuted ? (
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" />
            </svg>
          )}
          <span className="audio-btn-text">{isMuted ? "MUTED" : "AUDIO"}</span>
        </button>

        {/* Emergency Indicator & Sound Trigger */}
        <button
          type="button"
          className={`emergency-btn ${isEmergency ? "is-active" : ""}`}
          title="Emergency alert status (Click to trigger/test Master Warning Klaxon)"
          onClick={() => {
            soundEffects.playMasterWarning(2400);
          }}
        >
          <span className="emergency-icon">⚠</span>
          <span>EMERGENCY</span>
        </button>
      </div>
    </header>
  );
}
