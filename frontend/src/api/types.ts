// Aliases over the GENERATED OpenAPI types. Nothing here defines a new wire shape:
// every type points back into `generated/schema.d.ts`, which is produced from the
// live FastAPI app by `make contracts` and must never be edited by hand.
import type { components } from "./generated/schema";

type Schemas = components["schemas"];

export type SystemSnapshot = Schemas["SystemSnapshot"];
export type PilotSnapshot = Schemas["PilotSnapshot"];
export type PilotObservation = Schemas["PilotObservation"];
export type PilotId = Schemas["PilotId"];
export type AircraftTelemetry = Schemas["AircraftTelemetry"];
export type GuardianIncident = Schemas["GuardianIncident"];
export type GuardianState = Schemas["GuardianState"];
export type SentinelState = Schemas["SentinelState"];
export type SentinelDecision = Schemas["SentinelDecision"];
export type SimulatorActionType = Schemas["SimulatorActionType"];
export type SimulatorActionPayload = Schemas["SimulatorActionPayload"];
export type ScenarioMetadata = Schemas["ScenarioMetadata"];
export type ScenarioListResponse = Schemas["ScenarioListResponse"];
export type ScenarioStartRequest = Schemas["ScenarioStartRequest"];
export type ScenarioAdvanceRequest = Schemas["ScenarioAdvanceRequest"];
export type ScenarioResetRequest = Schemas["ScenarioResetRequest"];
export type PilotAcknowledgement = Schemas["PilotAcknowledgement"];
export type ATCDecision = Schemas["ATCDecision"];
export type ATCDecisionType = Schemas["ATCDecisionType"];
export type CommunicationLinkRequest = Schemas["CommunicationLinkRequest"];
export type CommandResponse = Schemas["CommandResponse"];
export type IncidentListResponse = Schemas["IncidentListResponse"];
export type EventHistoryResponse = Schemas["EventHistoryResponse"];
export type HealthResponse = Schemas["HealthResponse"];
export type StoredEvent = Schemas["StoredEvent"];
export type EventType = Schemas["EventType"];

/**
 * event_type -> payload model, mirroring the discriminator map in
 * backend/app/contracts/models.py. The generated `StoredEvent.payload` is a plain
 * union, so this map lets the UI narrow a payload once it has checked event_type.
 */
export interface EventPayloadMap {
  SCENARIO_STARTED: Schemas["ScenarioStartedPayload"];
  SCENARIO_ADVANCED: Schemas["ScenarioAdvancedPayload"];
  PILOT_OBSERVATION: Schemas["PilotObservation"];
  TELEMETRY_UPDATED: Schemas["AircraftTelemetry"];
  PILOT_ACKNOWLEDGED: Schemas["PilotAcknowledgement"];
  ATC_LINK_CHANGED: Schemas["ATCLinkChangedPayload"];
  GUARDIAN_INCIDENT: Schemas["GuardianIncident"];
  ATC_DECISION: Schemas["ATCDecision"];
  SENTINEL_DECISION: Schemas["SentinelDecision"];
  SIMULATOR_ACTION: Schemas["SimulatorActionPayload"];
  SCENARIO_RESET: Schemas["ScenarioResetPayload"];
  SCENARIO_COMPLETED: Schemas["ScenarioCompletedPayload"];
}

// Compile-time guard: fails typecheck if the backend adds or removes an EventType.
type _MapCoversEveryEventType = [EventType] extends [keyof EventPayloadMap]
  ? [keyof EventPayloadMap] extends [EventType]
    ? true
    : never
  : never;
export const EVENT_MAP_IS_EXHAUSTIVE: _MapCoversEveryEventType = true;

export type TypedEvent<T extends EventType> = StoredEvent & {
  event_type: T;
  payload: EventPayloadMap[T];
};

export function isEventOfType<T extends EventType>(event: StoredEvent, type: T): event is TypedEvent<T> {
  return event.event_type === type;
}

/** Runtime list of symbolic actions, checked against the generated union both ways. */
export const SIMULATOR_ACTIONS = [
  "NO_OP",
  "SIM_HOLD_STATE",
  "SIM_STABILIZE",
  "SIM_SCRIPTED_DIVERSION",
  "SIM_ABORT",
] as const satisfies readonly SimulatorActionType[];
type _ActionsComplete = SimulatorActionType extends (typeof SIMULATOR_ACTIONS)[number] ? true : never;
export const ACTIONS_ARE_EXHAUSTIVE: _ActionsComplete = true;

export const PILOT_IDS = ["PILOT_1", "PILOT_2"] as const satisfies readonly PilotId[];

/** Stable scenario IDs frozen in bootstrap section 11. The labels shown come from the API. */
export const CANONICAL_SCENARIO_IDS = [
  "normal_flight",
  "single_pilot_unresponsive",
  "dual_pilot_atc_connected",
  "dual_pilot_atc_disconnected",
  "camera_obstructed",
] as const;
