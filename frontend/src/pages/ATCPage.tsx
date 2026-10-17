import { useMemo, useState } from "react";
import { eventLabel } from "../api/events";
import { SIMULATOR_ACTIONS, type SimulatorActionType, type SystemSnapshot } from "../api/types";
import { formatVirtualTime, humanize, shortId } from "../components/format";
import { IncidentCard, SentinelDecisionList } from "../components/StatePanels";
import { SENTINEL_TONE } from "../components/tones";
import { Empty, Field, Panel, Pill } from "../components/ui";
import { eventsForRun, resolveEvidence, sentinelDecisions } from "../hooks/selectors";
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
  if (snapshot.sentinel_state !== "AWAITING_ATC")
    return `Sentinel is not awaiting simulated ATC (state: ${humanize(snapshot.sentinel_state)}).`;
  if (pending) return "Another command is in flight.";
  return null;
}

export function ATCPage() {
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

  if (!snapshot) return <Empty>Loading simulated ATC state…</Empty>;

  const blocker = decisionBlocker(snapshot, pending);
  const operatorValid = operatorId.trim().length > 0;
  const link = snapshot.communication;

  return (
    <div className="grid grid--atc">
      <div className="atc-disclaimer" role="note">
        Fictional ATC console for the simulation. It is not a real ATC system and not an authentication mechanism.
      </div>

      <Panel
        title="Simulated ATC link"
        subtitle="Scenario input — distinct from this browser's connection to the backend"
        actions={<Pill tone={link.atc_link_connected ? "ok" : "alert"}>{link.atc_link_connected ? "Connected" : "Disconnected"}</Pill>}
      >
        <dl className="fields fields--2">
          <Field label="Last change (virtual)" mono>
            {formatVirtualTime(link.last_change_at)}
          </Field>
          <Field label="Sentinel state">
            <Pill tone={SENTINEL_TONE[snapshot.sentinel_state]}>{humanize(snapshot.sentinel_state)}</Pill>
          </Field>
          <Field label="Remote sync (mock)">{link.remote_sync_connected ? "Connected" : "Not connected"}</Field>
          <Field label="Pending sync" mono>
            {link.pending_sync_count}
          </Field>
        </dl>
      </Panel>

      <Panel title="Active incident & evidence" className="atc-incident">
        {incident ? (
          <IncidentCard incident={incident}>
            <h4 className="subhead">Supporting evidence</h4>
            <ul className="evidence">
              {evidence.map(({ id, event }) => (
                <li key={id} className="evidence__row">
                  <span className="mono meta">{shortId(id)}</span>
                  {event ? (
                    <>
                      <span>{eventLabel(event.event_type)}</span>
                      {event.event_type === "PILOT_OBSERVATION" && "pilot_id" in event.payload && "observation_status" in event.payload && (
                        <span className="meta">
                          {event.payload.pilot_id} · {humanize(event.payload.observation_status)} · quality{" "}
                          {Math.round(event.payload.observation_quality * 100)}%
                        </span>
                      )}
                      <span className="meta mono">#{event.seq}</span>
                    </>
                  ) : (
                    <span className="meta">Not in loaded history window</span>
                  )}
                </li>
              ))}
            </ul>
          </IncidentCard>
        ) : (
          <Empty>No active incident. Decisions can only reference the active run's incident.</Empty>
        )}
      </Panel>

      <Panel title="ATC decision" subtitle="Sent to the backend; Sentinel and the simulator validate it independently">
        <form
          className="atc-form"
          onSubmit={(e) => {
            e.preventDefault();
          }}
        >
          <label className="input">
            <span className="field__label">Requested symbolic action</span>
            <select value={action} onChange={(e) => setAction(e.target.value as SimulatorActionType)} disabled={blocker !== null}>
              {APPROVABLE_ACTIONS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>
          <label className="input">
            <span className="field__label">Operator ID (fictional)</span>
            <input value={operatorId} maxLength={64} onChange={(e) => setOperatorId(e.target.value)} aria-invalid={!operatorValid} />
          </label>
          {!operatorValid && <p className="text-warn">Operator ID is required.</p>}
          <div className="btn-row">
            <button
              type="button"
              className="btn btn--ok"
              disabled={blocker !== null || !operatorValid}
              onClick={() => commands.atcDecision("APPROVE", action, operatorId.trim())}
            >
              Approve {action}
            </button>
            <button
              type="button"
              className="btn btn--danger"
              disabled={blocker !== null || !operatorValid}
              onClick={() => commands.atcDecision("REJECT", action, operatorId.trim())}
            >
              Reject
            </button>
          </div>
          {blocker && <p className="meta" data-testid="decision-blocker">{blocker}</p>}
        </form>
      </Panel>

      <Panel title="Sentinel decisions & outcome" subtitle="Authoritative results from the backend for this incident">
        <div className="last-action">
          <span className="field__label">Last permitted simulator action</span>
          {snapshot.last_simulator_action ? (
            <div className="last-action__body">
              <Pill tone="ok">{snapshot.last_simulator_action.action_type}</Pill>
              <span className="meta">
                {humanize(snapshot.last_simulator_action.result)} · {snapshot.last_simulator_action.reason}
              </span>
            </div>
          ) : (
            <span className="meta">None executed in this run.</span>
          )}
        </div>
        <SentinelDecisionList decisions={decisions} />
      </Panel>
    </div>
  );
}
