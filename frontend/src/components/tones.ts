// Maps each canonical enum value to a visual tone. `Record<Union, ...>` makes the
// typecheck fail if the backend ever adds a state we have not styled.
import type { components } from "../api/generated/schema";

type Schemas = components["schemas"];
export type GuardianState = Schemas["GuardianState"];
export type SentinelState = Schemas["SentinelState"];
export type PilotObservationStatus = Schemas["PilotObservationStatus"];
export type DecisionResult = Schemas["DecisionResult"];
export type EventType = Schemas["EventType"];

export type Tone = "ok" | "info" | "warn" | "alert" | "muted";

export const GUARDIAN_TONE: Record<GuardianState, Tone> = {
  NORMAL: "ok",
  SUSPECTED: "warn",
  AWAITING_ACK: "warn",
  ESCALATED: "alert",
  RECOVERING: "info",
};

export const SENTINEL_TONE: Record<SentinelState, Tone> = {
  STANDBY: "muted",
  AWAITING_ATC: "warn",
  LOCAL_FALLBACK: "alert",
  SIM_ACTION_RUNNING: "info",
  COMPLETED: "ok",
  ABORTED: "alert",
};

export const OBSERVATION_TONE: Record<PilotObservationStatus, Tone> = {
  RESPONSIVE: "ok",
  POSSIBLY_UNRESPONSIVE: "alert",
  UNKNOWN: "muted",
};

export const RESULT_TONE: Record<DecisionResult, Tone> = {
  PENDING: "warn",
  APPROVED: "info",
  REJECTED: "muted",
  EXECUTED: "ok",
  FAILED: "alert",
};

export const EVENT_TONE: Record<EventType, Tone> = {
  SCENARIO_STARTED: "info",
  SCENARIO_ADVANCED: "muted",
  PILOT_OBSERVATION: "muted",
  TELEMETRY_UPDATED: "muted",
  PILOT_ACKNOWLEDGED: "ok",
  ATC_LINK_CHANGED: "info",
  GUARDIAN_INCIDENT: "alert",
  ATC_DECISION: "warn",
  SENTINEL_DECISION: "warn",
  SIMULATOR_ACTION: "ok",
  SCENARIO_RESET: "info",
  SCENARIO_COMPLETED: "info",
};

/** Guardian escalation scale (ordered); RECOVERING is an off-track state. */
export const GUARDIAN_TRACK: GuardianState[] = ["NORMAL", "SUSPECTED", "AWAITING_ACK", "ESCALATED"];
export const GUARDIAN_ALTERNATES: GuardianState[] = ["RECOVERING"];

/** Sentinel's main authorization path; fallback/abort are off-track states. */
export const SENTINEL_TRACK: SentinelState[] = ["STANDBY", "AWAITING_ATC", "SIM_ACTION_RUNNING", "COMPLETED"];
export const SENTINEL_ALTERNATES: SentinelState[] = ["LOCAL_FALLBACK", "ABORTED"];
