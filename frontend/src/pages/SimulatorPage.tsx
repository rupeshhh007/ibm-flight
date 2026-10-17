import { useMemo } from "react";
import { FlightDisplay } from "../components/FlightDisplay";
import { formatNumber } from "../components/format";
import { Empty } from "../components/ui";
import { eventsForRun, telemetryTrack } from "../hooks/selectors";
import { useAeroGuard } from "../hooks/useAeroGuard";

export function SimulatorPage() {
  const { snapshot, events, pending, commands } = useAeroGuard();

  const runEvents = useMemo(() => eventsForRun(events, snapshot?.scenario_run_id), [events, snapshot?.scenario_run_id]);
  const track = useMemo(() => telemetryTrack(runEvents), [runEvents]);
  const telemetry = snapshot?.telemetry;

  if (!snapshot) return <Empty>Loading Simulator avionics telemetry…</Empty>;

  return (
    <div className="simulator-page-layout">
      {/* Flight Display & Telemetry Gauges */}
      <div className="simulator-grid">
        <div className="cyber-card area-flight-display">
          <div className="cyber-card-header">
            <span className="cyber-card-title">SYNTHETIC 2D FLIGHT TRACK</span>
            <span className="mono text-cyan">
              {telemetry ? `${telemetry.latitude.toFixed(4)}°N, ${telemetry.longitude.toFixed(4)}°E` : "—"}
            </span>
          </div>
          <FlightDisplay track={track} actionLabel={snapshot.last_simulator_action?.action_type ?? null} />
        </div>

        <div className="cyber-card area-gauges">
          <div className="cyber-card-header">
            <span className="cyber-card-title">PRIMARY FLIGHT INSTRUMENTS</span>
          </div>

          <div className="instruments-grid">
            <div className="instrument-dial">
              <span className="dial-label">AIRSPEED</span>
              <span className="dial-value mono text-highlight">
                {telemetry ? formatNumber(telemetry.airspeed_kts) : 450} <small>KT</small>
              </span>
            </div>

            <div className="instrument-dial">
              <span className="dial-label">ALTITUDE</span>
              <span className="dial-value mono text-highlight">
                {telemetry ? formatNumber(telemetry.altitude_ft) : 35000} <small>FT</small>
              </span>
            </div>

            <div className="instrument-dial">
              <span className="dial-label">HEADING</span>
              <span className="dial-value mono text-highlight">
                {telemetry ? String(Math.round(telemetry.heading_deg)).padStart(3, "0") : "090"}°
              </span>
            </div>

            <div className="instrument-dial">
              <span className="dial-label">FLIGHT PHASE</span>
              <span className="dial-value mono text-highlight">
                {telemetry ? telemetry.flight_phase : "CRUISE"}
              </span>
            </div>
          </div>

          <div className="simulator-controls-box">
            <span className="subhead">Flight Controls</span>
            <div className="btn-row">
              <button
                type="button"
                className="btn btn--primary"
                disabled={pending !== null || !snapshot.scenario_run_id}
                onClick={() => commands.advance(1000)}
              >
                Advance +1000 ms
              </button>
              <button
                type="button"
                className="btn btn--ghost"
                disabled={pending !== null || !snapshot.scenario_run_id}
                onClick={() => commands.reset()}
              >
                Reset Run
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
