// Maps each canonical enum value to a visual tone. `Record<Union, ...>` makes the
// typecheck fail if the backend ever adds a state we have not styled.
import type { components } from "../api/generated/schema";

type Schemas = components["schemas"];
export type GuardianState = Schemas["GuardianState"];
export type SentinelState = Schemas["SentinelState"];
export type PilotObservationStatus = Schemas["PilotObservationStatus"];

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

/** Guardian states in escalation order, used for the state ladder. */
export const GUARDIAN_LADDER: GuardianState[] = ["NORMAL", "SUSPECTED", "AWAITING_ACK", "ESCALATED", "RECOVERING"];
export const SENTINEL_LADDER: SentinelState[] = [
  "STANDBY",
  "AWAITING_ATC",
  "LOCAL_FALLBACK",
  "SIM_ACTION_RUNNING",
  "COMPLETED",
  "ABORTED",
];
