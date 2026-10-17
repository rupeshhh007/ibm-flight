import { useMemo, useState } from "react";
import { SIMULATOR_ACTIONS, type SimulatorActionType } from "../api/types";
import { shortId } from "../components/format";
import { Empty, Pill } from "../components/ui";
import { eventsForRun, sentinelDecisions } from "../hooks/selectors";
import { useAeroGuard } from "../hooks/useAeroGuard";
import { decisionBlocker } from "./ATCPage";

const APPROVABLE_ACTIONS = SIMULATOR_ACTIONS.filter((a): a is Exclude<SimulatorActionType, "NO_OP"> => a !== "NO_OP");

export function SentinelPage() {
  const { snapshot, events, pending, commands } = useAeroGuard();
  const [action, setAction] = useState<SimulatorActionType>("SIM_STABILIZE");
  const [operatorId] = useState("fictional-atc-demo");

  const runEvents = useMemo(() => eventsForRun(events, snapshot?.scenario_run_id), [events, snapshot?.scenario_run_id]);
  const incident = snapshot?.active_incident ?? null;
  const decisions = useMemo(
    () => sentinelDecisions(runEvents).filter((d) => !incident || d.decision.incident_id === incident.incident_id),
    [runEvents, incident],
  );

  if (!snapshot) return <Empty>Loading Sentinel & ATC telemetry…</Empty>;

  const blocker = decisionBlocker(snapshot, pending);
  const link = snapshot.communication;
  const isApproved = decisions.some((d) => d.decision.result === "APPROVED" || d.decision.result === "EXECUTED" || d.decision.authorization_source === "SIMULATED_ATC") || snapshot.sentinel_state === "COMPLETED";

  return (
    <div className="sentinel-page-layout">
      {/* Header bar */}
      <div className="sentinel-header-strip">
        <div className="sentinel-title-group">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#38bdf8" strokeWidth="2">
            <circle cx="12" cy="12" r="2" />
            <path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49" />
          </svg>
          <h2 className="sentinel-header-title">ATC COMMUNICATION</h2>
        </div>

        <div className="sentinel-header-link">
          <Pill tone={link.atc_link_connected ? "ok" : "alert"}>
            {link.atc_link_connected ? "CONNECTED · ATC Link Active" : "DISCONNECTED · Link Offline"}
          </Pill>
        </div>
      </div>

      <div className="sentinel-main-grid">
        {/* Left Column: Radio Message Dialogue & Audio Visualizer */}
        <div className="cyber-card sentinel-chat-card">
          <div className="cyber-card-header">
            <span className="cyber-card-title">RADIO TRANSMISSION LOG</span>
            <span className="mono text-dim text-small">VHF 124.85 MHz</span>
          </div>

          <div className="chat-messages-container">
            <div className="chat-bubble chat-bubble--atc">
              <div className="chat-bubble-header">
                <span className="chat-sender mono">ATC</span>
                <span className="chat-time mono">12:09:15</span>
              </div>
              <div className="chat-bubble-text">
                SIM-001, confirm your status. Radar shows no steering inputs.
              </div>
            </div>

            <div className="chat-bubble chat-bubble--aeroguard">
              <div className="chat-bubble-header">
                <span className="chat-sender mono">AEROGUARD</span>
                <span className="chat-time mono">12:09:17</span>
              </div>
              <div className="chat-bubble-text">
                No response from both pilots. Requesting emergency authorization.
              </div>
            </div>

            <div className={`chat-bubble chat-bubble--atc ${isApproved ? "chat-bubble--approved" : ""}`}>
              <div className="chat-bubble-header">
                <span className="chat-sender mono">ATC</span>
                <span className="chat-time mono">12:09:22</span>
              </div>
              <div className="chat-bubble-text">
                {isApproved
                  ? "Emergency authorization approved. You are cleared to execute stabilization."
                  : blocker
                  ? "Stand by, evaluating situational telemetry and priority airspace."
                  : "SIM-001, authorization pending operator confirmation."}
              </div>
            </div>

            {isApproved && (
              <div className="chat-bubble chat-bubble--aeroguard chat-bubble--success">
                <div className="chat-bubble-header">
                  <span className="chat-sender mono">AEROGUARD</span>
                  <span className="chat-time mono">12:09:23</span>
                </div>
                <div className="chat-bubble-text">
                  Authorization received. Executing stabilization sequence.
                </div>
              </div>
            )}
          </div>

          {/* Audio Spectrum Waveform Visualizer */}
          <div className="radio-visualizer-container">
            <div className="soundwave-bars" aria-hidden="true">
              {Array.from({ length: 48 }, (_, i) => {
                const height = Math.max(15, Math.sin(i * 0.4) * 50 + 40);
                return (
                  <span
                    key={i}
                    className="wave-bar"
                    style={{ height: `${height}%`, animationDelay: `${(i % 8) * 0.1}s` }}
                  />
                );
              })}
            </div>
            <div className="radio-freq-indicator mono">
              <span>ACTIVE FREQUENCY</span>
              <span className="text-cyan">124.850 MHz</span>
            </div>
          </div>
        </div>

        {/* Right Column: Authorization Card & Controls */}
        <div className="cyber-card sentinel-auth-card">
          <div className="cyber-card-header">
            <span className="cyber-card-title">AUTHORIZATION</span>
            <span className={`auth-badge ${isApproved ? "auth--approved" : snapshot.sentinel_state === "AWAITING_ATC" ? "auth--pending" : "auth--standby"}`}>
              {isApproved ? "✓ APPROVED" : snapshot.sentinel_state === "AWAITING_ATC" ? "⏳ PENDING" : "STANDBY"}
            </span>
          </div>

          <div className="auth-card-body">
            <div className="auth-details-grid">
              <div className="auth-field">
                <span className="auth-label">Valid for incident</span>
                <span className="auth-val mono">{incident ? shortId(incident.incident_id) : "INC-2024-001"}</span>
              </div>
              <div className="auth-field">
                <span className="auth-label">Expires at</span>
                <span className="auth-val mono text-alert">00:15:00</span>
              </div>
            </div>

            {/* Electronic Signature */}
            <div className="atc-signature-block">
              <span className="auth-label">ATC CONTROL SIGNATURE</span>
              <svg viewBox="0 0 200 45" className="signature-svg">
                <path
                  d="M 10 25 Q 30 5, 50 25 T 90 25 T 130 10 T 170 30 T 190 20"
                  fill="none"
                  stroke={isApproved ? "#10b981" : "#38bdf8"}
                  strokeWidth="2"
                />
              </svg>
            </div>

            {/* Link Quality Meter */}
            <div className="link-quality-block">
              <div className="quality-label-row">
                <span className="auth-label">ATC LINK QUALITY</span>
                <span className="mono text-cyan">98%</span>
              </div>
              <div className="link-meter-track">
                <div className="link-meter-fill" style={{ width: "98%" }} />
              </div>
            </div>

            {/* Decision Blocker for Tests */}
            <div data-testid="decision-blocker" className="decision-hint-box">
              {blocker ? (
                <span className="text-warn">{blocker}</span>
              ) : (
                <span className="text-ok">Decision required: Sentinel is awaiting simulated ATC authorization.</span>
              )}
            </div>

            {/* Action selector & Buttons */}
            <div className="atc-action-controls">
              <label className="field-select-row">
                <span className="auth-label">Action:</span>
                <select
                  value={action}
                  onChange={(e) => setAction(e.target.value as SimulatorActionType)}
                  disabled={Boolean(blocker)}
                  className="cyber-select"
                >
                  {APPROVABLE_ACTIONS.map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </select>
              </label>

              <div className="decision-btn-row">
                <button
                  type="button"
                  className="btn btn--primary btn--approve"
                  disabled={Boolean(blocker)}
                  onClick={() => commands.atcDecision("APPROVE", action, operatorId)}
                >
                  Approve {action}
                </button>
                <button
                  type="button"
                  className="btn btn--ghost btn--reject"
                  disabled={Boolean(blocker)}
                  onClick={() => commands.atcDecision("REJECT", "NO_OP", operatorId)}
                >
                  Reject
                </button>
              </div>

              {/* Link toggle for simulation */}
              <div className="link-toggle-row">
                <button
                  type="button"
                  className="btn btn--small btn--ghost"
                  onClick={() => commands.setLink(!link.atc_link_connected)}
                  disabled={pending !== null}
                >
                  {link.atc_link_connected ? "Simulate Disconnection" : "Reconnect Simulated Link"}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
