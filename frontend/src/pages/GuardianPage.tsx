import { useMemo } from "react";
import { CockpitCameraFeed } from "../components/CockpitCameraFeed";
import { formatVirtualTime, humanize, shortId } from "../components/format";
import { GUARDIAN_LADDER, GUARDIAN_TONE } from "../components/tones";
import { Empty, Pill } from "../components/ui";
import { eventsForRun, resolveEvidence } from "../hooks/selectors";
import { useAeroGuard } from "../hooks/useAeroGuard";

export function GuardianPage() {
  const { snapshot, events, pending, commands } = useAeroGuard();

  const incident = snapshot?.active_incident ?? null;
  const isEscalated = snapshot?.guardian_state === "ESCALATED" || Boolean(incident);

  const runEvents = useMemo(() => eventsForRun(events, snapshot?.scenario_run_id), [events, snapshot?.scenario_run_id]);
  const evidence = useMemo(() => (incident ? resolveEvidence(runEvents, incident.evidence_event_ids) : []), [runEvents, incident]);

  const pilot1 = snapshot?.pilots.find((p) => p.pilot_id === "PILOT_1") ?? {
    pilot_id: "PILOT_1",
    latest_observation: null,
  };
  const pilot2 = snapshot?.pilots.find((p) => p.pilot_id === "PILOT_2") ?? {
    pilot_id: "PILOT_2",
    latest_observation: null,
  };

  if (!snapshot) return <Empty>Loading Guardian incident agent…</Empty>;

  const simTime = snapshot.virtual_time ? formatVirtualTime(snapshot.virtual_time) : "00:10:14";

  return (
    <div className="guardian-page-layout">
      {/* Top Incident Banner */}
      <div className={`guardian-incident-banner ${isEscalated ? "is-incident" : "is-nominal"}`}>
        <div className="banner-top-row">
          <div className="incident-status-pill">
            <span className="pulse-indicator" />
            <span className="incident-status-title">
              {isEscalated ? "INCIDENT DETECTED" : "ALL SYSTEMS NOMINAL"}
            </span>
          </div>
          <div className="incident-sim-time mono">
            <span className="time-val">{simTime}</span>
            <span className="time-sub">SIMULATION TIME</span>
          </div>
        </div>

        <div className="incident-content-box">
          <div className="incident-icon-box">
            <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="M12 8v4m0 4h.01" />
            </svg>
          </div>

          <div className="incident-meta-info">
            <h2 className="incident-title">
              {incident ? humanize(incident.incident_type) : "NORMAL FLIGHT MONITORING"}
            </h2>
            <div className="incident-severity-row">
              <span className="severity-badge">{incident?.severity ?? "NORMAL"}</span>
              <span className="rule-badge mono">{incident?.incident_id ? shortId(incident.incident_id) : "G-DET-1"}</span>
            </div>
            <p className="incident-desc">
              {incident
                ? "Both pilots show sustained non-responsiveness based on visual and behavioral analysis."
                : "Guardian is actively correlating synthetic pilot observations and virtual acknowledgements."}
            </p>
          </div>

          <div className="incident-state-escalation">
            <div className={`escalated-indicator ${snapshot.guardian_state === "ESCALATED" ? "active" : ""}`}>
              {snapshot.guardian_state}
            </div>
          </div>
        </div>

        {/* State Pipeline Stepper */}
        <div className="state-pipeline-stepper" role="group" aria-label="Guardian state pipeline">
          {GUARDIAN_LADDER.map((step, idx) => {
            const isCurrent = snapshot.guardian_state === step;
            const stepTone = GUARDIAN_TONE[step];
            return (
              <div key={step} className={`pipeline-node ${isCurrent ? `is-active tone--${stepTone}` : ""}`}>
                <div className="pipeline-dot">
                  <span className="inner-dot" />
                </div>
                <span className="pipeline-label">{humanize(step)}</span>
                {idx < GUARDIAN_LADDER.length - 1 && <div className="pipeline-connector" />}
              </div>
            );
          })}
        </div>
      </div>

      {/* Middle Grid: Evidence & Latest Frames */}
      <div className="guardian-grid-row">
        {/* Evidence List Card */}
        <div className="cyber-card area-evidence">
          <div className="cyber-card-header">
            <h3 className="cyber-card-title">EVIDENCE ({evidence.length > 0 ? `${evidence.length}/${evidence.length}` : "0/0"})</h3>
            <Pill tone={evidence.length > 0 ? "alert" : "muted"}>Observations</Pill>
          </div>
          <div className="evidence-list-container">
            {evidence.length > 0 ? (
              <ul className="evidence-list">
                {evidence.map(({ id, event }, i) => (
                  <li key={id} className="evidence-item">
                    <div className="evidence-time mono">
                      ⏱ {event?.payload && "observed_at" in event.payload && typeof event.payload.observed_at === "string" ? formatVirtualTime(event.payload.observed_at) : simTime}
                    </div>
                    <div className="evidence-detail">
                      <span className="evidence-text">
                        {event?.payload && "pilot_id" in event.payload ? String(event.payload.pilot_id) : "Pilot"}:{" "}
                        {event?.payload && "observation_status" in event.payload ? humanize(String(event.payload.observation_status)) : "Observation"}
                        {event?.payload && "observation_quality" in event.payload && typeof event.payload.observation_quality === "number" ? ` (confidence ${event.payload.observation_quality.toFixed(2)})` : ""}
                      </span>
                    </div>
                    <span className="evidence-tag mono">E{i + 1}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>No incident evidence registered. Advance the scenario to populate observations.</Empty>
            )}
          </div>
        </div>

        {/* Latest Cockpit Frames */}
        <div className="cyber-card area-frames">
          <div className="cyber-card-header">
            <h3 className="cyber-card-title">LATEST FRAMES</h3>
            <div className="ack-buttons-row">
              <button
                type="button"
                className="btn btn--small btn--primary"
                disabled={pending !== null || !incident}
                onClick={() => commands.acknowledge("PILOT_1")}
              >
                Acknowledge as Pilot 1
              </button>
              <button
                type="button"
                className="btn btn--small btn--ghost"
                disabled={pending !== null || !incident}
                onClick={() => commands.acknowledge("PILOT_2")}
              >
                Acknowledge as Pilot 2
              </button>
            </div>
          </div>
          <div className="latest-frames-grid">
            <CockpitCameraFeed pilot={pilot1} role="Captain" />
            <CockpitCameraFeed pilot={pilot2} role="First Officer" />
          </div>
        </div>
      </div>
    </div>
  );
}
