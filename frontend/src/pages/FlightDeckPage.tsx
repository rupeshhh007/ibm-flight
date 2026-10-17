import { useMemo } from "react";
import { CockpitCameraFeed } from "../components/CockpitCameraFeed";
import { TacticalFlightMap } from "../components/TacticalFlightMap";
import { humanize } from "../components/format";
import { Empty } from "../components/ui";
import { useAeroGuard } from "../hooks/useAeroGuard";
import { soundEffects } from "../utils/soundEffects";

export function FlightDeckPage() {
  const { snapshot, events, pending, commands } = useAeroGuard();

  const incidentTitle = snapshot?.active_incident?.incident_type ? humanize(snapshot.active_incident.incident_type) : "Loss of Response";

  const pilot1 = snapshot?.pilots.find((p) => p.pilot_id === "PILOT_1") ?? {
    pilot_id: "PILOT_1",
    latest_observation: null,
  };
  const pilot2 = snapshot?.pilots.find((p) => p.pilot_id === "PILOT_2") ?? {
    pilot_id: "PILOT_2",
    latest_observation: null,
  };

  const runEvents = useMemo(() => {
    if (!snapshot?.scenario_run_id) return [];
    return events.filter((e) => e.scenario_run_id === snapshot.scenario_run_id);
  }, [events, snapshot?.scenario_run_id]);

  const progressPercent = Math.min(100, Math.round((runEvents.length / 18) * 100));

  if (!snapshot) return <Empty>Loading Flight Deck telemetry…</Empty>;

  return (
    <div className="flight-deck-layout">
      {/* Top Grid: Tactical Flight Map & Systems Status */}
      <div className="flight-deck-main-grid">
        {/* Realistic Interactive Satellite Tactical Map */}
        <div className="tactical-map-container">
          <TacticalFlightMap
            telemetry={snapshot.telemetry}
            isIncident={Boolean(snapshot.active_incident)}
            incidentLabel={incidentTitle}
            runEventsCount={runEvents.length}
          />
        </div>

        {/* Aircraft Systems Status Card */}
        <div className="aircraft-systems-card">
          <div className="systems-card-header">
            <span className="systems-title">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="9" />
                <line x1="12" y1="3" x2="12" y2="7" />
                <line x1="12" y1="17" x2="12" y2="21" />
                <line x1="3" y1="12" x2="7" y2="12" />
                <line x1="17" y1="12" x2="21" y2="12" />
              </svg>
              AIRCRAFT STATUS
            </span>
          </div>

          <div className="systems-wireframe-container">
            <svg viewBox="0 0 160 180" className="aircraft-wireframe-svg">
              <defs>
                <linearGradient id="wireframeGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#0284c7" stopOpacity="0.4" />
                </linearGradient>
              </defs>
              {/* Aircraft wireframe silhouette */}
              <path
                d="M 80 15 
                   C 83 25, 85 45, 85 85 
                   L 145 105 L 145 116 L 85 105 
                   L 84 145 L 105 155 L 105 162 L 80 158 
                   L 55 162 L 55 155 L 76 145 
                   L 75 105 L 15 116 L 15 105 L 75 85 
                   C 75 45, 77 25, 80 15 Z"
                fill="none"
                stroke="url(#wireframeGrad)"
                strokeWidth="1.5"
              />
              {/* Engine positions */}
              <circle cx="108" cy="98" r="4" fill="#10b981" />
              <circle cx="52" cy="98" r="4" fill="#10b981" />
              <line x1="80" y1="30" x2="80" y2="155" stroke="rgba(56, 189, 248, 0.2)" strokeDasharray="2 2" />
            </svg>

            <div className="systems-metrics-overlay">
              <div className="system-metric-row">
                <span className="metric-label">ENG 1</span>
                <span className="metric-val mono text-ok">98%</span>
              </div>
              <div className="system-metric-row">
                <span className="metric-label">ENG 2</span>
                <span className="metric-val mono text-ok">97%</span>
              </div>
              <div className="system-metric-row">
                <span className="metric-label">FUEL</span>
                <span className="metric-val mono text-cyan">72%</span>
              </div>
              <div className="system-metric-row">
                <span className="metric-label">HYDRAULICS</span>
                <span className="metric-val mono text-ok">OK</span>
              </div>
              <div className="system-metric-row">
                <span className="metric-label">AUTOPILOT</span>
                <span className="metric-val mono text-cyan">
                  {snapshot.last_simulator_action?.action_type ?? "ENGAGED"}
                </span>
              </div>
            </div>

            {/* Avionics Audio Soundboard Strip */}
            <div className="audio-soundboard-strip">
              <span className="soundboard-title">AVIONICS SOUND SYSTEM</span>
              <div className="soundboard-buttons">
                <button
                  type="button"
                  className="sound-cue-btn sound-cue-warning"
                  title="Test Master Warning Klaxon (Dual-Pilot Emergency)"
                  onClick={() => soundEffects.playMasterWarning(2400)}
                >
                  🚨 Klaxon Alert
                </button>
                <button
                  type="button"
                  className="sound-cue-btn sound-cue-caution"
                  title="Test Master Caution Ding-Dong Chime"
                  onClick={() => soundEffects.playMasterCaution()}
                >
                  ⚠️ Caution Chime
                </button>
                <button
                  type="button"
                  className="sound-cue-btn sound-cue-atc"
                  title="Test ATC Radio Transmission Chime"
                  onClick={() => soundEffects.playATCRadioChime()}
                >
                  📻 ATC Radio
                </button>
                <button
                  type="button"
                  className="sound-cue-btn sound-cue-ack"
                  title="Test Pilot Acknowledgment Confirm Chime"
                  onClick={() => soundEffects.playAckChime()}
                >
                  ✅ Pilot Ack
                </button>
                <button
                  type="button"
                  className="sound-cue-btn sound-cue-action"
                  title="Test Stabilize Action Lock Tone"
                  onClick={() => soundEffects.playActionTone()}
                >
                  🛡️ Stabilize
                </button>
                <button
                  type="button"
                  className="sound-cue-btn"
                  title="Test Camera Obstructed Caution Tone"
                  onClick={() => soundEffects.playSensorCaution()}
                >
                  👁️ Sensor Blip
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Dual Pilot Monitoring Feeds */}
        <div className="pilot-feeds-column">
          <CockpitCameraFeed
            pilot={pilot1}
            role="Captain"
            onAcknowledge={snapshot.active_incident ? () => commands.acknowledge("PILOT_1") : undefined}
            ackDisabled={pending !== null}
          />
          <CockpitCameraFeed
            pilot={pilot2}
            role="First Officer"
            onAcknowledge={snapshot.active_incident ? () => commands.acknowledge("PILOT_2") : undefined}
            ackDisabled={pending !== null}
          />
        </div>
      </div>

      {/* Bottom Status & Quick Scenario Advance Ribbon */}
      <div className="flight-deck-bottom-ribbon">
        <div className="agent-status-tile">
          <div className="agent-tile-icon guardian-color">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <div>
            <span className="tile-title">GUARDIAN</span>
            <span className="tile-status mono">{humanize(snapshot.guardian_state)}</span>
          </div>
        </div>

        <div className="agent-status-tile">
          <div className="agent-tile-icon sentinel-color">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="2" />
              <path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49" />
            </svg>
          </div>
          <div>
            <span className="tile-title">SENTINEL</span>
            <span className="tile-status mono">
              {snapshot.communication.atc_link_connected ? "ATC Connected" : "ATC Offline"}
            </span>
          </div>
        </div>

        <div className="agent-status-tile">
          <div className="agent-tile-icon vision-color">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M23 7l-7 5 7 5V7z" />
              <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
            </svg>
          </div>
          <div>
            <span className="tile-title">VISION</span>
            <span className="tile-status mono">2 Cameras Active</span>
          </div>
        </div>

        <div className="agent-status-tile">
          <div className="agent-tile-icon simulator-color">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
            </svg>
          </div>
          <div>
            <span className="tile-title">SIMULATOR</span>
            <span className="tile-status mono">Running</span>
          </div>
        </div>

        <div className="scenario-progress-tile">
          <div className="scenario-meta">
            <span className="tile-title">SCENARIO</span>
            <span className="scenario-name text-alert">{snapshot.scenario_id ? humanize(snapshot.scenario_id) : "Normal Flight"}</span>
          </div>
          <div className="progress-info">
            <div className="progress-bar-track">
              <div className="progress-bar-fill" style={{ width: `${progressPercent}%` }} />
            </div>
            <div className="progress-text-row mono">
              <span>{runEvents.length} / 18 events</span>
              <span>{progressPercent}%</span>
            </div>
          </div>
        </div>

        <div className="quick-advance-controls">
          <button
            type="button"
            className="btn btn--primary btn--compact"
            disabled={pending !== null || !snapshot.scenario_run_id}
            onClick={() => commands.advance(1000)}
          >
            Advance +1000 ms
          </button>
          <button
            type="button"
            className="btn btn--ghost btn--compact"
            disabled={pending !== null || !snapshot.scenario_run_id}
            onClick={() => commands.reset()}
          >
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}
