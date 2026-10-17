from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, ClassVar, Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import (
    ATCDecisionType,
    AuthorizationSource,
    DecisionResult,
    EventSource,
    EventType,
    FlightPhase,
    GuardianState,
    IncidentSeverity,
    IncidentType,
    PilotId,
    PilotObservationStatus,
    SentinelState,
    SimulatorActionType,
)


class ContractModel(BaseModel):
    # FastAPI decodes JSON before validation, so UUIDs/enums/timestamps must accept
    # their standard JSON string representation. Field types, bounds, validators,
    # and forbidden extras still make the public boundary strict and closed.
    model_config = ConfigDict(extra="forbid")


class UtcModel(ContractModel):
    @field_validator("*", mode="after")
    @classmethod
    def normalize_datetimes(cls, value: object) -> object:
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("datetime must be timezone-aware")
            return value.astimezone(timezone.utc)
        return value


class PilotObservation(UtcModel):
    pilot_id: PilotId
    observed_at: datetime
    observation_status: PilotObservationStatus
    camera_available: bool
    face_visible: bool
    eyes_closed: bool
    observation_duration_ms: Annotated[int, Field(ge=0, le=600_000)]
    observation_quality: Annotated[float, Field(ge=0.0, le=1.0)]

    @model_validator(mode="after")
    def uncertain_camera_is_unknown(self) -> PilotObservation:
        if (not self.camera_available or not self.face_visible) and self.observation_status != PilotObservationStatus.UNKNOWN:
            raise ValueError("unavailable or obscured camera evidence must be UNKNOWN")
        return self


class AircraftTelemetry(UtcModel):
    aircraft_id: Annotated[str, Field(min_length=1, max_length=64)]
    simulation_time: datetime
    altitude_ft: Annotated[float, Field(ge=-1_500, le=70_000)]
    airspeed_kts: Annotated[float, Field(ge=0, le=800)]
    heading_deg: Annotated[float, Field(ge=0, lt=360)]
    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]
    flight_phase: FlightPhase
    active_warning_codes: Annotated[list[Annotated[str, Field(min_length=1, max_length=64)]], Field(max_length=32)]


class PilotAcknowledgement(UtcModel):
    command_id: UUID
    scenario_run_id: UUID
    pilot_id: PilotId
    alert_id: UUID
    acknowledged_at: datetime


class GuardianIncident(UtcModel):
    incident_id: UUID
    scenario_run_id: UUID
    incident_type: IncidentType
    severity: IncidentSeverity
    guardian_state: GuardianState
    evidence_event_ids: Annotated[list[UUID], Field(min_length=1, max_length=64)]
    explanation: Annotated[str, Field(min_length=1, max_length=1000)]
    acknowledgement_required: bool
    created_at: datetime


class ATCDecision(UtcModel):
    command_id: UUID
    scenario_run_id: UUID
    incident_id: UUID
    decision: ATCDecisionType
    requested_action: SimulatorActionType
    operator_id: Annotated[str, Field(min_length=1, max_length=128)]
    issued_at: datetime


class SentinelDecision(UtcModel):
    decision_id: UUID
    scenario_run_id: UUID
    incident_id: UUID
    sentinel_state: SentinelState
    action_type: SimulatorActionType
    authorization_source: AuthorizationSource
    reason: Annotated[str, Field(min_length=1, max_length=1000)]
    evidence_event_ids: Annotated[list[UUID], Field(max_length=64)]
    executed_at: datetime
    result: DecisionResult


class CommunicationStatus(UtcModel):
    atc_link_connected: bool
    last_change_at: datetime
    remote_sync_connected: bool = False
    pending_sync_count: Annotated[int, Field(ge=0)] = 0


class ScenarioStartedPayload(UtcModel):
    scenario_id: str
    started_at: datetime


class ScenarioAdvancedPayload(UtcModel):
    delta_ms: Annotated[int, Field(ge=1, le=600_000)]
    virtual_time: datetime


class ATCLinkChangedPayload(UtcModel):
    command_id: UUID
    atc_link_connected: bool
    changed_at: datetime


class SimulatorActionPayload(UtcModel):
    action_id: UUID
    scenario_run_id: UUID
    action_type: SimulatorActionType
    authorization_source: AuthorizationSource
    authorized: bool
    result: DecisionResult
    reason: Annotated[str, Field(min_length=1, max_length=1000)]
    applied_at: datetime


class ScenarioResetPayload(UtcModel):
    command_id: UUID
    previous_scenario_run_id: UUID
    new_scenario_run_id: UUID
    reset_at: datetime


class ScenarioCompletedPayload(UtcModel):
    scenario_id: str
    completed_at: datetime


EventPayload: TypeAlias = (
    ScenarioStartedPayload
    | ScenarioAdvancedPayload
    | PilotObservation
    | AircraftTelemetry
    | PilotAcknowledgement
    | ATCLinkChangedPayload
    | GuardianIncident
    | ATCDecision
    | SentinelDecision
    | SimulatorActionPayload
    | ScenarioResetPayload
    | ScenarioCompletedPayload
)


class DomainEvent(UtcModel):
    event_id: UUID
    schema_version: Literal["1.0"] = "1.0"
    event_type: EventType
    occurred_at: datetime
    source: EventSource
    scenario_run_id: UUID
    correlation_id: UUID
    causation_event_id: UUID | None = None
    payload: EventPayload

    _payload_types: ClassVar[dict[EventType, type[BaseModel]]] = {
        EventType.SCENARIO_STARTED: ScenarioStartedPayload,
        EventType.SCENARIO_ADVANCED: ScenarioAdvancedPayload,
        EventType.PILOT_OBSERVATION: PilotObservation,
        EventType.TELEMETRY_UPDATED: AircraftTelemetry,
        EventType.PILOT_ACKNOWLEDGED: PilotAcknowledgement,
        EventType.ATC_LINK_CHANGED: ATCLinkChangedPayload,
        EventType.GUARDIAN_INCIDENT: GuardianIncident,
        EventType.ATC_DECISION: ATCDecision,
        EventType.SENTINEL_DECISION: SentinelDecision,
        EventType.SIMULATOR_ACTION: SimulatorActionPayload,
        EventType.SCENARIO_RESET: ScenarioResetPayload,
        EventType.SCENARIO_COMPLETED: ScenarioCompletedPayload,
    }

    @model_validator(mode="after")
    def event_type_matches_payload(self) -> DomainEvent:
        expected = self._payload_types[self.event_type]
        if type(self.payload) is not expected:
            raise ValueError(f"{self.event_type} requires payload {expected.__name__}")
        return self


class StoredEvent(DomainEvent):
    seq: Annotated[int, Field(gt=0)]


class PilotSnapshot(ContractModel):
    pilot_id: PilotId
    latest_observation: PilotObservation | None = None


class SystemSnapshot(UtcModel):
    scenario_id: str | None = None
    scenario_run_id: UUID | None = None
    virtual_time: datetime | None = None
    pilots: Annotated[list[PilotSnapshot], Field(min_length=2, max_length=2)]
    telemetry: AircraftTelemetry | None = None
    guardian_state: GuardianState = GuardianState.NORMAL
    sentinel_state: SentinelState = SentinelState.STANDBY
    active_incident: GuardianIncident | None = None
    communication: CommunicationStatus
    last_simulator_action: SimulatorActionPayload | None = None
    latest_event_seq: Annotated[int, Field(ge=0)] = 0
    status_text: str = "SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE"

    @model_validator(mode="after")
    def exactly_one_snapshot_per_pilot(self) -> SystemSnapshot:
        if {item.pilot_id for item in self.pilots} != {PilotId.PILOT_1, PilotId.PILOT_2}:
            raise ValueError("snapshot must contain exactly PILOT_1 and PILOT_2")
        return self


class ScenarioMetadata(ContractModel):
    scenario_id: str
    name: str
    description: str
    p0_behavior: str


class ScenarioListResponse(ContractModel):
    scenarios: list[ScenarioMetadata]


class ScenarioStartRequest(ContractModel):
    command_id: UUID
    scenario_id: str


class ScenarioAdvanceRequest(ContractModel):
    command_id: UUID
    scenario_run_id: UUID
    delta_ms: Annotated[int, Field(ge=1, le=600_000)]


class ScenarioResetRequest(ContractModel):
    command_id: UUID
    scenario_run_id: UUID


class CommunicationLinkRequest(UtcModel):
    command_id: UUID
    scenario_run_id: UUID
    atc_link_connected: bool
    changed_at: datetime


class CommandResponse(ContractModel):
    command_id: UUID
    accepted: bool
    duplicate: bool = False
    message: str
    snapshot: SystemSnapshot
    events: list[StoredEvent]


class EventHistoryResponse(ContractModel):
    events: list[StoredEvent]
    after_seq: Annotated[int, Field(ge=0)]
    limit: Annotated[int, Field(ge=1, le=500)]
    latest_event_seq: Annotated[int, Field(ge=0)]


class IncidentListResponse(ContractModel):
    incidents: list[GuardianIncident]


class HealthResponse(ContractModel):
    status: Literal["ok", "ready"]
    simulation_only: Literal[True] = True


class CommonApiError(ContractModel):
    code: str
    message: str
    details: list[str] = Field(default_factory=list)


class CommandRecord(ContractModel):
    command_id: UUID
    fingerprint: str
    result_json: str
