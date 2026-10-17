// Pure derivations over the ordered event list. Kept separate from React so
// they are easy to unit test.
import { isEventOfType, type AircraftTelemetry, type SentinelDecision, type StoredEvent } from "../api/types";

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
