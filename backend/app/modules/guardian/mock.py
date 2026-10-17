from dataclasses import dataclass
from uuid import UUID, uuid4

from app.contracts.enums import (
    EventType,
    GuardianState,
    IncidentSeverity,
    IncidentType,
    PilotId,
    PilotObservationStatus,
)
from app.contracts.models import GuardianIncident, PilotAcknowledgement, PilotObservation, StoredEvent


@dataclass(frozen=True)
class GuardianThresholds:
    dual_pilot_observations_required: int = 2


class MockGuardianAgent:
    def __init__(self, thresholds: GuardianThresholds | None = None) -> None:
        self.thresholds = thresholds or GuardianThresholds()
        self._state = GuardianState.NORMAL
        self._run_id: UUID | None = None
        self._active_incident: GuardianIncident | None = None
        self._concerns = {pilot_id: 0 for pilot_id in PilotId}
        self._latest: dict[PilotId, PilotObservationStatus] = {}
        self._evidence: list[UUID] = []

    @property
    def state(self) -> GuardianState:
        return self._state

    @property
    def active_incident(self) -> GuardianIncident | None:
        return self._active_incident

    def reset(self, scenario_run_id: UUID) -> None:
        self._run_id = scenario_run_id
        self._state = GuardianState.NORMAL
        self._active_incident = None
        self._concerns = {pilot_id: 0 for pilot_id in PilotId}
        self._latest = {}
        self._evidence = []

    def consume_observation(self, event: StoredEvent) -> GuardianIncident | None:
        if event.event_type != EventType.PILOT_OBSERVATION or not isinstance(event.payload, PilotObservation):
            raise ValueError("Guardian accepts only stored PILOT_OBSERVATION events")
        if event.scenario_run_id != self._run_id:
            raise ValueError("Guardian rejected stale scenario_run_id")
        observation = event.payload
        self._latest[observation.pilot_id] = observation.observation_status
        if observation.observation_status == PilotObservationStatus.UNKNOWN:
            return None
        if observation.observation_status == PilotObservationStatus.RESPONSIVE:
            self._concerns[observation.pilot_id] = 0
            if self._state != GuardianState.NORMAL:
                self._state = GuardianState.RECOVERING
            return None
        self._concerns[observation.pilot_id] += 1
        self._evidence.append(event.event_id)
        if any(status == PilotObservationStatus.RESPONSIVE for status in self._latest.values()):
            self._state = GuardianState.AWAITING_ACK
            return None
        if all(self._concerns[pilot_id] >= self.thresholds.dual_pilot_observations_required for pilot_id in PilotId):
            if self._active_incident is None:
                self._state = GuardianState.ESCALATED
                self._active_incident = GuardianIncident(
                    incident_id=uuid4(),
                    scenario_run_id=event.scenario_run_id,
                    incident_type=IncidentType.DUAL_PILOT_UNRESPONSIVE,
                    severity=IncidentSeverity.CRITICAL,
                    guardian_state=self._state,
                    evidence_event_ids=self._evidence[-4:],
                    explanation=(
                        "Rule G-P0-1: each pilot has at least "
                        f"{self.thresholds.dual_pilot_observations_required} usable synthetic concern observations "
                        "and no responsive peer observation or acknowledgement."
                    ),
                    acknowledgement_required=True,
                    created_at=event.occurred_at,
                )
            return self._active_incident
        self._state = GuardianState.AWAITING_ACK if len(self._latest) == 2 else GuardianState.SUSPECTED
        return None

    def acknowledge(self, acknowledgement: PilotAcknowledgement) -> None:
        if acknowledgement.scenario_run_id != self._run_id:
            raise ValueError("Guardian rejected stale scenario_run_id")
        self._state = GuardianState.RECOVERING
        self._active_incident = None
        self._concerns[acknowledgement.pilot_id] = 0
