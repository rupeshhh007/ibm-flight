import { useMemo, useState } from "react";
import { AuditTimeline } from "../components/AuditTimeline";
import { formatVirtualTime } from "../components/format";
import { Empty } from "../components/ui";
import { eventsForRun } from "../hooks/selectors";
import { useAeroGuard } from "../hooks/useAeroGuard";

export function BlackBoxPage() {
  const { snapshot, events } = useAeroGuard();
  const [activeSubTab, setActiveSubTab] = useState<"aircraft" | "cockpit" | "timeline" | "state">("timeline");
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<"1x" | "2x">("1x");

  const runEvents = useMemo(() => eventsForRun(events, snapshot?.scenario_run_id), [events, snapshot?.scenario_run_id]);

  if (!snapshot) return <Empty>Loading Black Box audit flight recorder…</Empty>;

  const simTime = snapshot.virtual_time ? formatVirtualTime(snapshot.virtual_time) : "00:10:14";

  return (
    <div className="blackbox-page-layout">
      {/* Header with Scrubber Controls */}
      <div className="blackbox-header-strip">
        <div className="blackbox-title-group">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#38bdf8" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <polygon points="10 8 16 12 10 16 10 8" />
          </svg>
          <h2 className="blackbox-header-title">BLACK BOX REPLAY</h2>
        </div>

        {/* Playback Controls & Timeline Scrubber */}
        <div className="blackbox-scrubber-controls">
          <div className="scrubber-slider-container">
            <input
              type="range"
              min="0"
              max={Math.max(1, runEvents.length)}
              value={runEvents.length}
              readOnly
              className="scrubber-slider"
            />
            <span className="scrubber-time mono">{simTime} / 00:18:00</span>
          </div>

          <div className="playback-btn-group">
            <button
              type="button"
              className="playback-btn"
              onClick={() => setIsPlaying(!isPlaying)}
              title={isPlaying ? "Pause" : "Play"}
            >
              {isPlaying ? "⏸" : "▶"}
            </button>
            <button
              type="button"
              className={`playback-speed-btn ${playbackSpeed === "1x" ? "is-active" : ""}`}
              onClick={() => setPlaybackSpeed(playbackSpeed === "1x" ? "2x" : "1x")}
            >
              {playbackSpeed}
            </button>
          </div>

          <div className="replay-mode-badge mono">
            <span className="badge-pulse" />
            <span>REPLAY MODE</span>
          </div>
        </div>
      </div>

      {/* Sub Tabs: Aircraft View, Cockpit View, Event Timeline, System State */}
      <div className="blackbox-subtabs-row">
        <button
          type="button"
          className={`subtab-btn ${activeSubTab === "aircraft" ? "is-active" : ""}`}
          onClick={() => setActiveSubTab("aircraft")}
        >
          ✈ Aircraft View
        </button>
        <button
          type="button"
          className={`subtab-btn ${activeSubTab === "cockpit" ? "is-active" : ""}`}
          onClick={() => setActiveSubTab("cockpit")}
        >
          👨‍✈ Cockpit View
        </button>
        <button
          type="button"
          className={`subtab-btn ${activeSubTab === "timeline" ? "is-active" : ""}`}
          onClick={() => setActiveSubTab("timeline")}
        >
          📋 Event Timeline
        </button>
        <button
          type="button"
          className={`subtab-btn ${activeSubTab === "state" ? "is-active" : ""}`}
          onClick={() => setActiveSubTab("state")}
        >
          ⚙ System State
        </button>
      </div>

      {/* Main Content Area */}
      <div className="blackbox-content-area">
        {activeSubTab === "timeline" && (
          <div className="cyber-card">
            <div className="cyber-card-header">
              <span className="cyber-card-title">FLIGHT EVENT RECORDER TIMELINE</span>
              <span className="mono text-cyan">{events.length} total events committed</span>
            </div>
            <AuditTimeline events={events} currentRunId={snapshot?.scenario_run_id} />
          </div>
        )}

        {activeSubTab === "aircraft" && (
          <div className="cyber-card">
            <div className="cyber-card-header">
              <span className="cyber-card-title">AIRCRAFT POSITION & TELEMETRY AUDIT</span>
            </div>
            <div className="telemetry-audit-grid">
              <div className="metric-item">
                <span className="metric-name">Altitude</span>
                <span className="metric-score mono">{snapshot.telemetry?.altitude_ft ?? 35000} FT</span>
              </div>
              <div className="metric-item">
                <span className="metric-name">Indicated Airspeed</span>
                <span className="metric-score mono">{snapshot.telemetry?.airspeed_kts ?? 450} KT</span>
              </div>
              <div className="metric-item">
                <span className="metric-name">Heading</span>
                <span className="metric-score mono">{snapshot.telemetry?.heading_deg ?? 90}°</span>
              </div>
              <div className="metric-item">
                <span className="metric-name">Flight Phase</span>
                <span className="metric-score mono">{snapshot.telemetry?.flight_phase ?? "CRUISE"}</span>
              </div>
            </div>
          </div>
        )}

        {activeSubTab === "cockpit" && (
          <div className="cyber-card">
            <div className="cyber-card-header">
              <span className="cyber-card-title">COCKPIT OBSERVATIONS AUDIT</span>
            </div>
            <p className="meta" style={{ padding: "16px" }}>
              Audio and video sensor evidence recorded in SQLite event stream with cryptographic ordering.
            </p>
          </div>
        )}

        {activeSubTab === "state" && (
          <div className="cyber-card">
            <div className="cyber-card-header">
              <span className="cyber-card-title">SYSTEM SNAPSHOT DUMP</span>
            </div>
            <pre className="mono raw-json-viewer">
              {JSON.stringify(snapshot, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
