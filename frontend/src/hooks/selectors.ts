// Pure derivations over the ordered event list. Kept separate from React so
// they are easy to unit test. Everything here is computed from events the
// backend actually committed — nothing is synthesised on the client.
import {
  isEventOfType,
  type AircraftTelemetry,
  type GuardianIncident,
  type PilotObservation,
  type SentinelDecision,
  type StoredEvent,
} from "../api/types";
import { humanize, pilotLabel } from "../components/format";
import { RESULT_TONE, type Tone } from "../components/tones";

export function eventsForRun(events: readonly StoredEvent[], runId: string | null | undefined): StoredEvent[] {
  return runId ? events.filter((event) => event.scenario_run_id === runId) : [];
}

export function sentinelDecisions(events: readonly StoredEvent[]): { seq: number; decision: SentinelDecision }[] {
  return events.filter((e) => isEventOfType(e, "SENTINEL_DECISION")).map((e) => ({ seq: e.seq, decision: e.payload as SentinelDecision }));
}

export function telemetryTrack(events: readonly StoredEvent[]): AircraftTelemetry[] {
  return events.filter((e) => isEventOfType(e, "TELEMETRY_UPDATED")).map((e) => e.payload as AircraftTelemetry);
}

/** Resolves an incident's evidence IDs to the stored events we have loaded (some may be outside the window). */
export function resolveEvidence(events: readonly StoredEvent[], evidenceIds: readonly string[]) {
  const byId = new Map(events.map((event) => [event.event_id, event]));
  return evidenceIds.map((id) => ({ id, event: byId.get(id) ?? null }));
}

export function observationOf(event: StoredEvent | null): PilotObservation | null {
  return event && isEventOfType(event, "PILOT_OBSERVATION") ? (event.payload as PilotObservation) : null;
}

/** Counts over the current run's pilot observations (raw fields, no invented thresholds). */
export interface ObservationSummary {
  total: number;
  responsive: number;
  possiblyUnresponsive: number;
  unknown: number;
  cameraUnavailable: number;
  faceNotVisible: number;
}

export function observationSummary(events: readonly StoredEvent[]): ObservationSummary {
  const summary: ObservationSummary = { total: 0, responsive: 0, possiblyUnresponsive: 0, unknown: 0, cameraUnavailable: 0, faceNotVisible: 0 };
  for (const event of events) {
    const obs = observationOf(event);
    if (!obs) continue;
    summary.total += 1;
    if (obs.observation_status === "RESPONSIVE") summary.responsive += 1;
    else if (obs.observation_status === "POSSIBLY_UNRESPONSIVE") summary.possiblyUnresponsive += 1;
    else summary.unknown += 1;
    if (!obs.camera_available) summary.cameraUnavailable += 1;
    if (!obs.face_visible) summary.faceNotVisible += 1;
  }
  return summary;
}

/** The telemetry sample at (or immediately before) the moment the incident was committed. */
export function incidentPosition(events: readonly StoredEvent[], incidentId: string | null | undefined): AircraftTelemetry | null {
  if (!incidentId) return null;
  let latest: AircraftTelemetry | null = null;
  for (const event of events) {
    if (isEventOfType(event, "TELEMETRY_UPDATED")) latest = event.payload as AircraftTelemetry;
    if (isEventOfType(event, "GUARDIAN_INCIDENT") && (event.payload as GuardianIncident).incident_id === incidentId) return latest;
  }
  return null;
}

/** A significant moment in a run, used for the horizontal run timeline. */
export interface Milestone {
  seq: number;
  at: string;
  label: string;
  detail: string;
  tone: Tone;
}

/** Key events of a run, in commit order. Routine ticks and responsive observations are omitted. */
export function runMilestones(events: readonly StoredEvent[]): Milestone[] {
  const out: Milestone[] = [];
  for (const e of events) {
    const base = { seq: e.seq, at: e.occurred_at };
    if (isEventOfType(e, "SCENARIO_STARTED")) out.push({ ...base, label: "Scenario start", detail: e.payload.scenario_id, tone: "info" });
    else if (isEventOfType(e, "SCENARIO_RESET")) out.push({ ...base, label: "Run reset", detail: "New run identity", tone: "info" });
    else if (isEventOfType(e, "PILOT_OBSERVATION") && e.payload.observation_status !== "RESPONSIVE")
      out.push({ ...base, label: `${pilotLabel(e.payload.pilot_id)} ${e.payload.observation_status === "UNKNOWN" ? "unknown" : "concern"}`, detail: humanize(e.payload.observation_status), tone: e.payload.observation_status === "UNKNOWN" ? "muted" : "warn" });
    else if (isEventOfType(e, "GUARDIAN_INCIDENT")) out.push({ ...base, label: "Incident", detail: humanize(e.payload.incident_type), tone: "alert" });
    else if (isEventOfType(e, "PILOT_ACKNOWLEDGED")) out.push({ ...base, label: "Acknowledged", detail: pilotLabel(e.payload.pilot_id), tone: "ok" });
    else if (isEventOfType(e, "ATC_LINK_CHANGED")) out.push({ ...base, label: e.payload.atc_link_connected ? "ATC link up" : "ATC link down", detail: "Simulated link", tone: e.payload.atc_link_connected ? "info" : "warn" });
    else if (isEventOfType(e, "ATC_DECISION")) out.push({ ...base, label: `ATC ${e.payload.decision === "APPROVE" ? "approve" : "reject"}`, detail: e.payload.requested_action, tone: e.payload.decision === "APPROVE" ? "ok" : "muted" });
    else if (isEventOfType(e, "SENTINEL_DECISION")) out.push({ ...base, label: `Sentinel ${humanize(e.payload.result).toLowerCase()}`, detail: e.payload.action_type, tone: RESULT_TONE[e.payload.result] });
    else if (isEventOfType(e, "SIMULATOR_ACTION")) out.push({ ...base, label: `Action ${humanize(e.payload.result).toLowerCase()}`, detail: e.payload.action_type, tone: e.payload.authorized && e.payload.result === "EXECUTED" ? "ok" : "alert" });
    else if (isEventOfType(e, "SCENARIO_COMPLETED")) out.push({ ...base, label: "Completed", detail: e.payload.scenario_id, tone: "info" });
  }
  return out;
}

/** One line of the ATC communication log. `side` places it like a two-party transcript. */
export interface CommsEntry {
  seq: number;
  at: string;
  side: "atc" | "aircraft" | "system";
  from: string;
  text: string;
  tone: Tone;
}

/**
 * The ATC console transcript, derived from committed authorization-related events.
 * These are the events themselves rendered as messages; no text is invented beyond
 * describing each event's fields.
 */
export function commsLog(events: readonly StoredEvent[]): CommsEntry[] {
  const out: CommsEntry[] = [];
  for (const e of events) {
    const base = { seq: e.seq, at: e.occurred_at };
    if (isEventOfType(e, "GUARDIAN_INCIDENT"))
      out.push({ ...base, side: "aircraft", from: "Guardian", text: `${humanize(e.payload.severity)} incident raised: ${humanize(e.payload.incident_type)}. ${e.payload.explanation}`, tone: "alert" });
    else if (isEventOfType(e, "SENTINEL_DECISION"))
      out.push({ ...base, side: "aircraft", from: "Sentinel", text: `${humanize(e.payload.result)} · ${e.payload.action_type} — ${e.payload.reason}`, tone: RESULT_TONE[e.payload.result] });
    else if (isEventOfType(e, "ATC_DECISION"))
      out.push({ ...base, side: "atc", from: `Simulated ATC · ${e.payload.operator_id}`, text: e.payload.decision === "APPROVE" ? `APPROVE ${e.payload.requested_action}` : `REJECT (requested ${e.payload.requested_action})`, tone: e.payload.decision === "APPROVE" ? "ok" : "muted" });
    else if (isEventOfType(e, "SIMULATOR_ACTION"))
      out.push({ ...base, side: "aircraft", from: "Simulator", text: `${humanize(e.payload.result)} ${e.payload.action_type} via ${humanize(e.payload.authorization_source)}. ${e.payload.reason}`, tone: e.payload.authorized && e.payload.result === "EXECUTED" ? "ok" : "alert" });
    else if (isEventOfType(e, "ATC_LINK_CHANGED"))
      out.push({ ...base, side: "system", from: "Link", text: e.payload.atc_link_connected ? "Simulated ATC link connected" : "Simulated ATC link disconnected — disconnection alone authorizes nothing", tone: e.payload.atc_link_connected ? "info" : "warn" });
    else if (isEventOfType(e, "PILOT_ACKNOWLEDGED"))
      out.push({ ...base, side: "aircraft", from: pilotLabel(e.payload.pilot_id), text: "Acknowledged the active alert", tone: "ok" });
  }
  return out;
}

/** The newest Sentinel decision for a given incident, if any. */
export function latestDecisionFor(events: readonly StoredEvent[], incidentId: string | null | undefined): { seq: number; decision: SentinelDecision } | null {
  if (!incidentId) return null;
  const list = sentinelDecisions(events).filter((d) => d.decision.incident_id === incidentId);
  return list.length ? list[list.length - 1] : null;
}

/** Telemetry samples of a run with their commit time, for the flight scene. */
export function sceneSamples(events: readonly StoredEvent[]): { at: string; telemetry: AircraftTelemetry }[] {
  return events.filter((e) => isEventOfType(e, "TELEMETRY_UPDATED")).map((e) => ({ at: e.occurred_at, telemetry: e.payload as AircraftTelemetry }));
}

/** When (virtual time) the given incident's GUARDIAN_INCIDENT event was committed. */
export function incidentEventTime(events: readonly StoredEvent[], incidentId: string | null | undefined): string | null {
  if (!incidentId) return null;
  const hit = events.find((e) => isEventOfType(e, "GUARDIAN_INCIDENT") && (e.payload as GuardianIncident).incident_id === incidentId);
  return hit ? hit.occurred_at : null;
}

/** One pilot's observations in commit order (for quality sparklines and timelines). */
export function pilotObservations(events: readonly StoredEvent[], pilotId: string): { seq: number; obs: PilotObservation }[] {
  return events
    .filter((e) => isEventOfType(e, "PILOT_OBSERVATION") && (e.payload as PilotObservation).pilot_id === pilotId)
    .map((e) => ({ seq: e.seq, obs: e.payload as PilotObservation }));
}

/** Count of non-responsive ("concern") observations per pilot in the given events. */
export function concernCounts(events: readonly StoredEvent[]): Record<string, number> {
  const out: Record<string, number> = { PILOT_1: 0, PILOT_2: 0 };
  for (const e of events) {
    const obs = observationOf(e);
    if (obs && obs.observation_status === "POSSIBLY_UNRESPONSIVE") out[obs.pilot_id] = (out[obs.pilot_id] ?? 0) + 1;
  }
  return out;
}
