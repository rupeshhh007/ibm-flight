// Test builders typed against the generated contract, so a contract change breaks the tests.
import type { Api } from "../api/client";
import type { GuardianIncident, ScenarioMetadata, StoredEvent, SystemSnapshot } from "../api/types";

export const RUN_ID = "11111111-1111-4111-8111-111111111111";
export const INCIDENT_ID = "22222222-2222-4222-8222-222222222222";

export function makeSnapshot(overrides: Partial<SystemSnapshot> = {}): SystemSnapshot {
  return {
    scenario_id: "dual_pilot_atc_connected",
    scenario_run_id: RUN_ID,
    virtual_time: "2026-01-01T00:00:02Z",
    pilots: [
      { pilot_id: "PILOT_1", latest_observation: null },
      { pilot_id: "PILOT_2", latest_observation: null },
    ],
    telemetry: null,
    guardian_state: "NORMAL",
    sentinel_state: "STANDBY",
    active_incident: null,
    communication: {
      atc_link_connected: true,
      last_change_at: "2026-01-01T00:00:00Z",
      remote_sync_connected: false,
      pending_sync_count: 0,
    },
    last_simulator_action: null,
    latest_event_seq: 5,
    status_text: "SIMULATION ONLY",
    ...overrides,
  };
}

export function makeIncident(overrides: Partial<GuardianIncident> = {}): GuardianIncident {
  return {
    incident_id: INCIDENT_ID,
    scenario_run_id: RUN_ID,
    incident_type: "DUAL_PILOT_UNRESPONSIVE",
    severity: "CRITICAL",
    guardian_state: "ESCALATED",
    evidence_event_ids: [],
    explanation: "rule X",
    acknowledgement_required: true,
    created_at: "2026-01-01T00:00:02Z",
    ...overrides,
  };
}

export function makeEvent(seq: number, overrides: Partial<StoredEvent> = {}): StoredEvent {
  return {
    seq,
    event_id: `00000000-0000-4000-8000-${String(seq).padStart(12, "0")}`,
    schema_version: "1.0",
    event_type: "SCENARIO_ADVANCED",
    occurred_at: "2026-01-01T00:00:01Z",
    source: "SCENARIO",
    scenario_run_id: RUN_ID,
    correlation_id: RUN_ID,
    causation_event_id: null,
    payload: { delta_ms: 1000, virtual_time: "2026-01-01T00:00:01Z" },
    ...overrides,
  };
}

export const SCENARIOS: ScenarioMetadata[] = [
  ["normal_flight", "Normal flight"],
  ["single_pilot_unresponsive", "Single pilot concern"],
  ["dual_pilot_atc_connected", "Dual pilot concern with simulated ATC"],
  ["dual_pilot_atc_disconnected", "Dual pilot concern without simulated ATC"],
  ["camera_obstructed", "Camera obstructed"],
].map(([scenario_id, name]) => ({ scenario_id, name, description: `${name} description`, p0_behavior: "behavior" }));

/** A fake API whose methods tests can override; unspecified commands fail loudly. */
export function makeClient(snapshot: SystemSnapshot, overrides: Partial<Api> = {}): Api {
  const fail = () => Promise.reject(new Error("unexpected call"));
  return {
    health: () => Promise.resolve({ status: "ok", simulation_only: true }),
    state: () => Promise.resolve(snapshot),
    scenarios: () => Promise.resolve({ scenarios: SCENARIOS }),
    incidents: () => Promise.resolve({ incidents: [] }),
    events: (afterSeq: number) => Promise.resolve({ after_seq: afterSeq, events: [], latest_event_seq: snapshot.latest_event_seq, limit: 500 }),
    startScenario: fail,
    advanceScenario: fail,
    resetScenario: fail,
    acknowledge: fail,
    atcDecision: fail,
    setLink: fail,
    ...overrides,
  };
}
