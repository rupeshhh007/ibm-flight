import { useMemo, useState } from "react";
import { SIMULATOR_ACTIONS, type SentinelDecision, type SimulatorActionType, type SystemSnapshot } from "../api/types";
import { Card, Chip, LinkScene, SectionHeader } from "../components/console";
import { formatClock, humanize, shortId } from "../components/format";
import { Icon, type IconName } from "../components/icons";
import { CommsLog } from "../components/Insights";
import { EvidenceTable, IncidentSummary, LastActionCard, SentinelDecisionList } from "../components/StatePanels";
import { SENTINEL_ALTERNATES, SENTINEL_TONE, SENTINEL_TRACK, type Tone } from "../components/tones";
import { Empty, Notice, StateTrack } from "../components/ui";
import { commsLog, eventsForRun, latestDecisionFor, resolveEvidence, sentinelDecisions } from "../hooks/selectors";
import { useAeroGuard } from "../hooks/useAeroGuard";

// APPROVE must request a real symbolic action, so NO_OP is not offered for approval.
const APPROVABLE_ACTIONS = SIMULATOR_ACTIONS.filter((a): a is Exclude<SimulatorActionType, "NO_OP"> => a !== "NO_OP");

/**
 * Why the decision buttons are disabled, or null if a decision can be sent.
 * This is a UX hint only — the backend re-validates everything and is authoritative.
 */
export function decisionBlocker(snapshot: SystemSnapshot | null, pending: string | null): string | null {
  if (!snapshot?.scenario_run_id) return "No active scenario run.";
  if (!snapshot.communication.atc_link_connected) return "Simulated ATC link is disconnected.";
  if (!snapshot.active_incident) return "No active incident is awaiting a decision.";
  if (snapshot.sentinel_state === "STANDBY")
    return "Sentinel is in Standby, not awaiting simulated ATC. In this build, reconnecting the link does not re-request authorization; reset the run to repeat the flow.";
  if (snapshot.sentinel_state !== "AWAITING_ATC")
    return `Sentinel is not awaiting simulated ATC (state: ${humanize(snapshot.sentinel_state)}).`;
  if (pending) return "Another command is in flight.";
  return null;
}

/** Headline authorization status, derived from the newest Sentinel decision for the active incident. */
export function authorizationStatus(
  snapshot: SystemSnapshot,
  latest: { decision: SentinelDecision } | null,
): { tone: Tone; icon: IconName; title: string; detail: string } {
  if (!snapshot.active_incident) return { tone: "muted", icon: "info", title: "No request", detail: "No active incident requires authorization." };
  const awaiting = snapshot.sentinel_state === "AWAITING_ATC";
  switch (latest?.decision.result) {
    case "EXECUTED":
      return latest.decision.authorization_source === "SIMULATED_ATC"
        ? { tone: "ok", icon: "check", title: "Approved · executed", detail: `Simulator executed ${latest.decision.action_type}.` }
        : { tone: "ok", icon: "check", title: "Executed", detail: `Simulator executed ${latest.decision.action_type} (authorization: ${humanize(latest.decision.authorization_source)}).` };
    case "PENDING":
      return awaiting
        ? { tone: "warn", icon: "clock", title: "Awaiting decision", detail: "Sentinel is waiting for an explicit simulated ATC decision." }
        : { tone: "warn", icon: "clock", title: "Pending", detail: `${latest.decision.reason} Sentinel state: ${humanize(snapshot.sentinel_state)}.` };
    case "APPROVED":
      return { tone: "info", icon: "check", title: "Approved", detail: `Action ${latest.decision.action_type} authorized; awaiting simulator result.` };
    case "REJECTED":
      return { tone: "muted", icon: "x", title: "Rejected", detail: awaiting ? "No action executed. Sentinel is still awaiting a valid decision." : "No action executed." };
    case "FAILED":
      return { tone: "alert", icon: "alert", title: "Failed", detail: latest.decision.reason };
    default:
      // No Sentinel decision has been recorded for this incident yet.
      return awaiting
        ? { tone: "warn", icon: "clock", title: "Awaiting decision", detail: "Sentinel is waiting for an explicit simulated ATC decision." }
        : { tone: "muted", icon: "info", title: "Not requested", detail: `Sentinel state: ${humanize(snapshot.sentinel_state)}.` };
  }
}

export function SentinelPage() {
  const { snapshot, events, pending, commands } = useAeroGuard();
  const [action, setAction] = useState<SimulatorActionType>("SIM_STABILIZE");
  const [operatorId, setOperatorId] = useState("fictional-atc-demo");

  const runEvents = useMemo(() => eventsForRun(events, snapshot?.scenario_run_id), [events, snapshot?.scenario_run_id]);
  const incident = snapshot?.active_incident ?? null;
  const decisions = useMemo(
    () => sentinelDecisions(runEvents).filter((d) => !incident || d.decision.incident_id === incident.incident_id),
    [runEvents, incident],
  );
  const evidence = useMemo(() => (incident ? resolveEvidence(runEvents, incident.evidence_event_ids) : []), [runEvents, incident]);
  const log = useMemo(() => commsLog(runEvents), [runEvents]);
  const latest = useMemo(() => latestDecisionFor(runEvents, incident?.incident_id), [runEvents, incident?.incident_id]);

  if (!snapshot) return <Empty>Loading Sentinel and simulated ATC state…</Empty>;

  const blocker = decisionBlocker(snapshot, pending);
  const operatorValid = operatorId.trim().length > 0;
  const link = snapshot.communication;
  const status = authorizationStatus(snapshot, latest);
  const executed = snapshot.last_simulator_action;

  return (
    <div className="view">
      <SectionHeader
        title="Sentinel"
        subtitle="ATC communication & authorization · fictional simulated console"
        tone={SENTINEL_TONE[snapshot.sentinel_state]}
        actions={
          <div className={`linkbox ${link.atc_link_connected ? "linkbox--ok" : "linkbox--alert"}`}>
            <span className="linkbox__label">Communication link</span>
            <strong>{link.atc_link_connected ? "Connected" : "Disconnected"}</strong>
            <Icon name={link.atc_link_connected ? "signal" : "unlink"} size={18} />
          </div>
        }
      />

      <Notice tone="info" title="Simulated authorization console.">
        Not a real ATC system and not an authentication mechanism. Approve and Reject only submit a command to the AeroGuard backend, where Sentinel and the simulator validate it independently.
      </Notice>

      <div className="g75">
        <div className="stack">
          <Card flush className="card--scene">
            <LinkScene connected={link.atc_link_connected} emergency={Boolean(incident)} aircraftId={snapshot.telemetry?.aircraft_id ?? "SIM"} />
          </Card>
          <Card title={`ATC communication (${log.length})`} icon="tower">
            <CommsLog entries={log} />
          </Card>
          <Card title="Active incident & evidence" icon="alert" tone={incident ? (incident.severity === "CRITICAL" ? "alert" : "warn") : undefined}>
            {incident ? (
              <IncidentSummary incident={incident}>
                <h4 className="subhead">Supporting evidence</h4>
                <EvidenceTable evidence={evidence} />
              </IncidentSummary>
            ) : (
              <Empty icon="shield">No active incident. Decisions can only reference the active run's incident.</Empty>
            )}
          </Card>
        </div>

        <div className="stack">
          <Card title="ATC decision" icon="shield" className="decision-card">
            <div className={`auth-status auth-status--${status.tone}`}>
              <span className="auth-status__icon" aria-hidden="true">
                <Icon name={status.icon} size={24} />
              </span>
              <div>
                <p className={`auth-status__title text-${status.tone}`}>{status.title}</p>
                <p className="auth-status__detail">{status.detail}</p>
              </div>
              {latest && <span className="auth-status__time mono">{formatClock(latest.decision.executed_at)}</span>}
            </div>
            <dl className="mini-grid">
              <div>
                <dt>Incident</dt>
                <dd className="mono">{incident ? `INC-${shortId(incident.incident_id)}` : "—"}</dd>
              </div>
              <div>
                <dt>Scenario run</dt>
                <dd className="mono">{shortId(snapshot.scenario_run_id)}</dd>
              </div>
              <div>
                <dt>Sentinel</dt>
                <dd>
                  <Chip tone={SENTINEL_TONE[snapshot.sentinel_state]}>{humanize(snapshot.sentinel_state)}</Chip>
                </dd>
              </div>
              <div>
                <dt>Last decision</dt>
                <dd className="mono">{latest ? `#${latest.seq}` : "—"}</dd>
              </div>
            </dl>

            <form className="form" onSubmit={(e) => e.preventDefault()}>
              <fieldset className="actions-list" disabled={blocker !== null}>
                <legend className="field__label">Symbolic action to authorize</legend>
                {APPROVABLE_ACTIONS.map((a, i) => {
                  const wasExecuted = executed?.action_type === a && executed.result === "EXECUTED";
                  return (
                    <label key={a} className={`action-row ${action === a ? "is-selected" : ""} ${wasExecuted ? "is-done" : ""}`}>
                      <input type="radio" name="sim-action" value={a} checked={action === a} onChange={() => setAction(a)} />
                      <span className="action-row__num">{i + 1}</span>
                      <span className="action-row__name">
                        {humanize(a)}
                        <span className="mono action-row__code">{a}</span>
                      </span>
                      <span className="action-row__state">
                        {wasExecuted ? (
                          <>
                            <Icon name="check" size={12} /> Executed {formatClock(executed?.applied_at)}
                          </>
                        ) : action === a ? (
                          "Selected"
                        ) : (
                          "Available"
                        )}
                      </span>
                    </label>
                  );
                })}
              </fieldset>
              <label className="field">
                <span className="field__label">Operator ID (fictional)</span>
                <input className="input" value={operatorId} maxLength={64} onChange={(e) => setOperatorId(e.target.value)} aria-invalid={!operatorValid} />
              </label>
              {!operatorValid && <p className="field__error">Operator ID is required.</p>}
              <div className="decision-actions">
                <button type="button" className="btn btn--approve" disabled={blocker !== null || !operatorValid} onClick={() => commands.atcDecision("APPROVE", action, operatorId.trim())}>
                  <Icon name="check" size={15} />
                  Approve {action}
                </button>
                <button type="button" className="btn btn--reject" disabled={blocker !== null || !operatorValid} onClick={() => commands.atcDecision("REJECT", action, operatorId.trim())}>
                  <Icon name="x" size={15} />
                  Reject
                </button>
              </div>
              {blocker && (
                <p className="hint hint--blocker" data-testid="decision-blocker">
                  <Icon name="info" size={13} /> {blocker}
                </p>
              )}
            </form>
          </Card>

          <Card title="Sentinel state" icon="radar">
            <StateTrack label="Sentinel state" steps={SENTINEL_TRACK} alternates={SENTINEL_ALTERNATES} current={snapshot.sentinel_state} toneOf={SENTINEL_TONE} format={humanize} />
            <LastActionCard action={executed} />
          </Card>

          <Card title={`Decision history (${decisions.length})`} icon="list">
            <SentinelDecisionList decisions={decisions} />
          </Card>
        </div>
      </div>
    </div>
  );
}
