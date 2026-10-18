import { describe, expect, it } from "vitest";
import type { StoredEvent } from "../api/types";
import { INCIDENT_ID, RUN_ID, makeEvent, makeIncident } from "../test/fixtures";
import { commsLog, incidentPosition, latestDecisionFor, observationSummary, runMilestones } from "./selectors";

const obs = (seq: number, pilot: "PILOT_1" | "PILOT_2", status: "RESPONSIVE" | "POSSIBLY_UNRESPONSIVE" | "UNKNOWN", extra: { camera_available?: boolean; face_visible?: boolean } = {}): StoredEvent =>
  makeEvent(seq, {
    event_type: "PILOT_OBSERVATION",
    source: "VISION",
    payload: {
      pilot_id: pilot,
      observed_at: "2026-01-01T00:00:01Z",
      observation_status: status,
      camera_available: extra.camera_available ?? true,
      face_visible: extra.face_visible ?? true,
      eyes_closed: status === "POSSIBLY_UNRESPONSIVE",
      observation_duration_ms: 1000,
      observation_quality: 0.9,
    },
  });

const telemetry = (seq: number, lat: number): StoredEvent =>
  makeEvent(seq, {
    event_type: "TELEMETRY_UPDATED",
    source: "SIMULATOR",
    payload: {
      aircraft_id: "SIM-1",
      simulation_time: "2026-01-01T00:00:01Z",
      altitude_ft: 35000,
      airspeed_kts: 450,
      heading_deg: 90,
      latitude: lat,
      longitude: 72,
      flight_phase: "CRUISE",
      active_warning_codes: [],
    },
  });

const incidentEvent = (seq: number): StoredEvent => makeEvent(seq, { event_type: "GUARDIAN_INCIDENT", source: "GUARDIAN", payload: makeIncident() });

const decision = (seq: number, result: "PENDING" | "REJECTED" | "EXECUTED", incidentId = INCIDENT_ID): StoredEvent =>
  makeEvent(seq, {
    event_type: "SENTINEL_DECISION",
    source: "SENTINEL",
    payload: {
      decision_id: `d-${seq}`,
      incident_id: incidentId,
      scenario_run_id: RUN_ID,
      sentinel_state: "AWAITING_ATC",
      action_type: result === "EXECUTED" ? "SIM_STABILIZE" : "NO_OP",
      authorization_source: result === "PENDING" ? "NONE" : "SIMULATED_ATC",
      reason: `reason ${seq}`,
      evidence_event_ids: [],
      executed_at: "2026-01-01T00:00:02Z",
      result,
    },
  });

describe("observationSummary", () => {
  it("counts raw observation fields without inventing thresholds", () => {
    const summary = observationSummary([
      obs(1, "PILOT_1", "RESPONSIVE"),
      obs(2, "PILOT_2", "POSSIBLY_UNRESPONSIVE"),
      obs(3, "PILOT_1", "UNKNOWN", { camera_available: false, face_visible: false }),
      telemetry(4, 10),
    ]);
    expect(summary).toEqual({ total: 3, responsive: 1, possiblyUnresponsive: 1, unknown: 1, cameraUnavailable: 1, faceNotVisible: 1 });
  });
});

describe("runMilestones", () => {
  it("keeps significant events in commit order and drops routine ticks and responsive observations", () => {
    const milestones = runMilestones([
      makeEvent(1, { event_type: "SCENARIO_STARTED", payload: { scenario_id: "dual_pilot_atc_connected", started_at: "2026-01-01T00:00:00Z" } }),
      makeEvent(2),
      telemetry(3, 10),
      obs(4, "PILOT_1", "RESPONSIVE"),
      obs(5, "PILOT_2", "POSSIBLY_UNRESPONSIVE"),
      incidentEvent(6),
      decision(7, "PENDING"),
    ]);
    expect(milestones.map((m) => m.seq)).toEqual([1, 5, 6, 7]);
    expect(milestones.map((m) => m.label)).toEqual(["Scenario start", "Pilot 2 concern", "Incident", "Sentinel pending"]);
    expect(milestones[2].tone).toBe("alert");
  });
});

describe("commsLog", () => {
  it("renders authorization events as a two-party transcript", () => {
    const log = commsLog([
      incidentEvent(1),
      makeEvent(2, {
        event_type: "ATC_DECISION",
        source: "SIMULATED_ATC",
        payload: { command_id: "c", scenario_run_id: RUN_ID, incident_id: INCIDENT_ID, decision: "REJECT", requested_action: "SIM_STABILIZE", operator_id: "op-1", issued_at: "2026-01-01T00:00:02Z" },
      }),
      decision(3, "REJECTED"),
      telemetry(4, 10),
    ]);
    expect(log.map((e) => [e.seq, e.side, e.from])).toEqual([
      [1, "aircraft", "Guardian"],
      [2, "atc", "Simulated ATC · op-1"],
      [3, "aircraft", "Sentinel"],
    ]);
    expect(log[1].text).toBe("REJECT (requested SIM_STABILIZE)");
  });
});

describe("incidentPosition", () => {
  it("uses the last telemetry sample committed before the incident", () => {
    const position = incidentPosition([telemetry(1, 10), telemetry(2, 11), incidentEvent(3), telemetry(4, 12)], INCIDENT_ID);
    expect(position?.latitude).toBe(11);
  });

  it("returns null without a matching incident", () => {
    expect(incidentPosition([telemetry(1, 10)], INCIDENT_ID)).toBeNull();
    expect(incidentPosition([telemetry(1, 10), incidentEvent(2)], null)).toBeNull();
  });
});

describe("latestDecisionFor", () => {
  it("returns the newest decision for the given incident only", () => {
    const events = [decision(1, "PENDING"), decision(2, "REJECTED"), decision(3, "EXECUTED", "other-incident")];
    expect(latestDecisionFor(events, INCIDENT_ID)?.seq).toBe(2);
    expect(latestDecisionFor(events, null)).toBeNull();
  });
});
