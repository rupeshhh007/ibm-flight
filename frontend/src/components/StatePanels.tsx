import type { ReactNode } from "react";
import type { GuardianIncident, GuardianState, SentinelDecision, SentinelState, SimulatorActionPayload } from "../api/types";
import { formatVirtualTime, humanize, shortId } from "./format";
import { GUARDIAN_LADDER, GUARDIAN_TONE, SENTINEL_LADDER, SENTINEL_TONE, type Tone } from "./tones";
import { Empty, Field, Ladder, Panel, Pill } from "./ui";

export function GuardianPanel({ state }: { state: GuardianState }) {
  return (
    <Panel
      title="Guardian monitoring agent"
      subtitle="Evaluates observations, telemetry and acknowledgements. Never controls the simulator."
      actions={<Pill tone={GUARDIAN_TONE[state]} pulse={state === "ESCALATED"}>{humanize(state)}</Pill>}
    >
      <Ladder steps={GUARDIAN_LADDER} current={state} toneOf={GUARDIAN_TONE} format={humanize} />
    </Panel>
  );
}

export function IncidentCard({ incident, children }: { incident: GuardianIncident; children?: ReactNode }) {
  const tone: Tone = incident.severity === "CRITICAL" ? "alert" : "warn";
  return (
    <article className={`incident incident--${tone}`} aria-label="Active incident">
      <header className="incident__head">
        <div>
          <p className="incident__eyebrow">{humanize(incident.severity)} incident</p>
          <h3 className="incident__title">{humanize(incident.incident_type)}</h3>
        </div>
        <Pill tone={tone} pulse>
          {humanize(incident.guardian_state)}
        </Pill>
      </header>
      <p className="incident__explanation">{incident.explanation}</p>
      <dl className="fields fields--3">
        <Field label="Incident ID" mono>
          {shortId(incident.incident_id)}
        </Field>
        <Field label="Created (virtual)" mono>
          {formatVirtualTime(incident.created_at)}
        </Field>
        <Field label="Evidence events" mono>
          {incident.evidence_event_ids.length}
        </Field>
      </dl>
      {incident.acknowledgement_required && <p className="note">Pilot acknowledgement requested.</p>}
      {children}
    </article>
  );
}

export function IncidentList({ incidents, activeId }: { incidents: GuardianIncident[]; activeId?: string | null }) {
  if (incidents.length === 0) return <Empty>No Guardian incidents recorded.</Empty>;
  return (
    <ul className="list">
      {[...incidents].reverse().map((incident) => (
        <li key={incident.incident_id} className="list__row">
          <Pill tone={incident.severity === "CRITICAL" ? "alert" : "warn"}>{humanize(incident.severity)}</Pill>
          <span className="list__main">{humanize(incident.incident_type)}</span>
          <span className="mono meta">{shortId(incident.incident_id)}</span>
          <span className="mono meta">run {shortId(incident.scenario_run_id)}</span>
          {incident.incident_id === activeId && <Pill tone="info">Active</Pill>}
        </li>
      ))}
    </ul>
  );
}

const RESULT_TONE: Record<SentinelDecision["result"], Tone> = {
  PENDING: "warn",
  APPROVED: "info",
  REJECTED: "muted",
  EXECUTED: "ok",
  FAILED: "alert",
};

export function SentinelDecisionList({ decisions }: { decisions: { seq: number; decision: SentinelDecision }[] }) {
  if (decisions.length === 0) return <Empty>No Sentinel decisions for this run yet.</Empty>;
  return (
    <ol className="decisions">
      {[...decisions].reverse().map(({ seq, decision }) => (
        <li key={seq} className="decision">
          <div className="decision__head">
            <Pill tone={RESULT_TONE[decision.result]}>{humanize(decision.result)}</Pill>
            <span className="decision__action mono">{decision.action_type}</span>
            <span className="meta mono">#{seq}</span>
          </div>
          <p className="decision__reason">{decision.reason}</p>
          <p className="meta">
            State {humanize(decision.sentinel_state)} · authorization {humanize(decision.authorization_source)} ·{" "}
            {decision.evidence_event_ids.length} evidence events · {formatVirtualTime(decision.executed_at)}
          </p>
        </li>
      ))}
    </ol>
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
      subtitle="Authoritative decisions. Only symbolic simulation actions — no real aircraft control."
      actions={<Pill tone={SENTINEL_TONE[state]} pulse={state === "AWAITING_ATC"}>{humanize(state)}</Pill>}
    >
      <Ladder steps={SENTINEL_LADDER} current={state} toneOf={SENTINEL_TONE} format={humanize} />
      <div className="last-action">
        <span className="field__label">Last permitted simulator action</span>
        {lastAction ? (
          <div className="last-action__body">
            <Pill tone={lastAction.authorized ? "ok" : "alert"}>{lastAction.action_type}</Pill>
            <span className="meta">
              {humanize(lastAction.result)} · via {humanize(lastAction.authorization_source)} · {formatVirtualTime(lastAction.applied_at)}
            </span>
          </div>
        ) : (
          <span className="meta">None executed in this run.</span>
        )}
      </div>
      <SentinelDecisionList decisions={decisions} />
    </Panel>
  );
}
