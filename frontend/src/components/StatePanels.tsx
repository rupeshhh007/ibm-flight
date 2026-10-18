import type { ReactNode } from "react";
import { eventLabel } from "../api/events";
import type { GuardianIncident, GuardianState, SentinelDecision, SentinelState, SimulatorActionPayload, StoredEvent } from "../api/types";
import { observationOf } from "../hooks/selectors";
import { formatClock, formatVirtualTime, humanize, pilotLabel, shortId } from "./format";
import { Icon } from "./icons";
import {
  GUARDIAN_ALTERNATES,
  GUARDIAN_TONE,
  GUARDIAN_TRACK,
  OBSERVATION_TONE,
  RESULT_TONE,
  SENTINEL_ALTERNATES,
  SENTINEL_TONE,
  SENTINEL_TRACK,
  type Tone,
} from "./tones";
import { Badge, Empty, KV, Panel, StateTrack } from "./ui";

export function GuardianPanel({ state }: { state: GuardianState }) {
  return (
    <Panel
      title="Guardian monitoring agent"
      icon="shield"
      description="Evaluates observations, telemetry and acknowledgements. Never controls the simulator."
      actions={<Badge tone={GUARDIAN_TONE[state]} live={state === "ESCALATED"} solid>{humanize(state)}</Badge>}
    >
      <StateTrack label="Guardian escalation level" steps={GUARDIAN_TRACK} alternates={GUARDIAN_ALTERNATES} current={state} toneOf={GUARDIAN_TONE} format={humanize} />
    </Panel>
  );
}

/** Headline block for the active incident: type, severity, rule explanation and identity. */
export function IncidentSummary({ incident, children }: { incident: GuardianIncident; children?: ReactNode }) {
  const tone: Tone = incident.severity === "CRITICAL" ? "alert" : "warn";
  return (
    <article className={`incident incident--${tone}`} aria-label="Active incident">
      <header className="incident__head">
        <span className={`incident__icon incident__icon--${tone}`} aria-hidden="true">
          <Icon name="alert" size={18} />
        </span>
        <div className="incident__heading">
          <p className="incident__eyebrow">
            <span className={`text-${tone}`}>{humanize(incident.severity)}</span> · Incident {shortId(incident.incident_id)}
          </p>
          <h3 className="incident__title">{humanize(incident.incident_type)}</h3>
        </div>
        <Badge tone={tone} solid live>
          {humanize(incident.guardian_state)}
        </Badge>
      </header>
      <p className="incident__explanation">{incident.explanation}</p>
      <dl className="kv kv--4">
        <KV label="Created (virtual)" mono>
          {formatClock(incident.created_at)}
        </KV>
        <KV label="Evidence" mono>
          {incident.evidence_event_ids.length} events
        </KV>
        <KV label="Acknowledgement">{incident.acknowledgement_required ? "Requested" : "Not required"}</KV>
        <KV label="Run" mono>
          {shortId(incident.scenario_run_id)}
        </KV>
      </dl>
      {children}
    </article>
  );
}

/** Evidence table: each evidence event ID resolved against the loaded history. */
export function EvidenceTable({ evidence }: { evidence: { id: string; event: StoredEvent | null }[] }) {
  if (evidence.length === 0) return <Empty>No evidence events attached.</Empty>;
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Time</th>
            <th scope="col">Event</th>
            <th scope="col">Detail</th>
            <th scope="col" className="num">Seq</th>
          </tr>
        </thead>
        <tbody>
          {evidence.map(({ id, event }, i) => {
            const obs = observationOf(event);
            return (
              <tr key={id}>
                <td className="mono muted-text">E{i + 1}</td>
                <td className="mono">{event ? formatClock(event.occurred_at) : "—"}</td>
                <td>{event ? eventLabel(event.event_type) : <span className="muted-text mono">{shortId(id)}</span>}</td>
                <td>
                  {obs ? (
                    <span className="cell-flex">
                      <span>{pilotLabel(obs.pilot_id)}</span>
                      <Badge tone={OBSERVATION_TONE[obs.observation_status]}>{humanize(obs.observation_status)}</Badge>
                      <span className="muted-text mono">q {obs.observation_quality.toFixed(2)}</span>
                    </span>
                  ) : event ? (
                    <span className="muted-text">{event.source}</span>
                  ) : (
                    <span className="muted-text">Not in loaded history window</span>
                  )}
                </td>
                <td className="mono num muted-text">{event ? event.seq : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function IncidentList({ incidents, activeId }: { incidents: GuardianIncident[]; activeId?: string | null }) {
  if (incidents.length === 0) return <Empty>No Guardian incidents recorded.</Empty>;
  return (
    <div className="table-wrap table-wrap--scroll" tabIndex={0} role="region" aria-label="Incident history, scrollable">
      <table className="table">
        <thead>
          <tr>
            <th scope="col">Severity</th>
            <th scope="col">Incident</th>
            <th scope="col">Created</th>
          </tr>
        </thead>
        <tbody>
          {[...incidents].reverse().map((incident) => (
            <tr key={incident.incident_id} className={incident.incident_id === activeId ? "is-active" : ""}>
              <td>
                <Badge tone={incident.severity === "CRITICAL" ? "alert" : "warn"}>{humanize(incident.severity)}</Badge>
              </td>
              <td>
                <span className="cell-stack">
                  <span>
                    {humanize(incident.incident_type)}
                    {incident.incident_id === activeId && <span className="tag">Active</span>}
                  </span>
                  <span className="mono muted-text">
                    {shortId(incident.incident_id)} · run {shortId(incident.scenario_run_id)}
                  </span>
                </span>
              </td>
              <td className="mono muted-text">{formatClock(incident.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SentinelDecisionList({ decisions }: { decisions: { seq: number; decision: SentinelDecision }[] }) {
  if (decisions.length === 0) return <Empty>No Sentinel decisions for this run yet.</Empty>;
  return (
    <ol className="decisions" tabIndex={0} aria-label="Sentinel decisions, newest first">
      {[...decisions].reverse().map(({ seq, decision }) => (
        <li key={seq} className={`decision decision--${RESULT_TONE[decision.result]}`}>
          <div className="decision__head">
            <Badge tone={RESULT_TONE[decision.result]} solid>
              {humanize(decision.result)}
            </Badge>
            <span className="decision__action mono">{decision.action_type}</span>
            <span className="muted-text mono">#{seq}</span>
          </div>
          <p className="decision__reason">{decision.reason}</p>
          <p className="decision__meta">
            {humanize(decision.sentinel_state)} · authorization {humanize(decision.authorization_source)} · {decision.evidence_event_ids.length} evidence ·{" "}
            {formatVirtualTime(decision.executed_at)}
          </p>
        </li>
      ))}
    </ol>
  );
}

export function LastActionCard({ action }: { action: SimulatorActionPayload | null | undefined }) {
  return (
    <div className={`last-action ${action ? (action.authorized && action.result === "EXECUTED" ? "last-action--ok" : "last-action--alert") : ""}`}>
      <span className="kv__label">Last permitted simulator action</span>
      {action ? (
        <div className="last-action__body">
          <Badge tone={action.authorized && action.result === "EXECUTED" ? "ok" : "alert"} icon={action.authorized ? "check" : "x"} solid>
            {action.action_type}
          </Badge>
          <span className="muted-text">
            {humanize(action.result)} · via {humanize(action.authorization_source)} · {formatClock(action.applied_at)}
          </span>
        </div>
      ) : (
        <span className="muted-text">None executed in this run.</span>
      )}
    </div>
  );
}

export function SentinelPanel({
  state,
  decisions,
  lastAction,
}: {
  state: SentinelState;
  decisions: { seq: number; decision: SentinelDecision }[];
  lastAction: SimulatorActionPayload | null | undefined;
}) {
  return (
    <Panel
      title="Sentinel emergency-response agent"
      icon="radar"
      description="Authoritative decisions. Only symbolic simulation actions — no real aircraft control."
      actions={<Badge tone={SENTINEL_TONE[state]} live={state === "AWAITING_ATC"} solid>{humanize(state)}</Badge>}
    >
      <StateTrack label="Sentinel state" steps={SENTINEL_TRACK} alternates={SENTINEL_ALTERNATES} current={state} toneOf={SENTINEL_TONE} format={humanize} />
      <LastActionCard action={lastAction} />
      <SentinelDecisionList decisions={decisions} />
    </Panel>
  );
}
