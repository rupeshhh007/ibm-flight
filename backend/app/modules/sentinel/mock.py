from datetime import datetime
from uuid import UUID, uuid4

from app.contracts.enums import (
    ATCDecisionType,
    AuthorizationSource,
    DecisionResult,
    GuardianState,
    IncidentType,
    SentinelState,
    SimulatorActionType,
)
from app.contracts.models import ATCDecision, GuardianIncident, SentinelDecision


class MockSentinelAgent:
    def __init__(self) -> None:
        self._state = SentinelState.STANDBY
        self._run_id: UUID | None = None
        self._atc_connected = True
        self._incident: GuardianIncident | None = None

    @property
    def state(self) -> SentinelState:
        return self._state

    def reset(self, scenario_run_id: UUID, atc_connected: bool) -> None:
        self._run_id = scenario_run_id
        self._atc_connected = atc_connected
        self._incident = None
        self._state = SentinelState.STANDBY

    def on_incident(self, incident: GuardianIncident, observed_at: datetime) -> SentinelDecision:
        if (
            incident.scenario_run_id != self._run_id
            or incident.guardian_state != GuardianState.ESCALATED
            or incident.incident_type != IncidentType.DUAL_PILOT_UNRESPONSIVE
        ):
            raise ValueError("Sentinel rejected invalid or stale Guardian incident")
        self._incident = incident
        self._state = SentinelState.AWAITING_ATC if self._atc_connected else SentinelState.STANDBY
        return SentinelDecision(
            decision_id=uuid4(),
            scenario_run_id=incident.scenario_run_id,
            incident_id=incident.incident_id,
            sentinel_state=self._state,
            action_type=SimulatorActionType.NO_OP,
            authorization_source=AuthorizationSource.NONE,
            reason=(
                "Waiting for explicit matching simulated ATC approval."
                if self._atc_connected
                else "ATC link is disconnected; disconnect alone does not authorize P0 fallback."
            ),
            evidence_event_ids=incident.evidence_event_ids,
            executed_at=observed_at,
            result=DecisionResult.PENDING,
        )

    def decide(self, decision: ATCDecision) -> SentinelDecision:
        if self._incident is None or decision.scenario_run_id != self._run_id:
            raise ValueError("Sentinel rejected stale scenario_run_id")
        if decision.incident_id != self._incident.incident_id:
            raise ValueError("Sentinel rejected mismatched incident_id")
        if not self._atc_connected or self._state != SentinelState.AWAITING_ATC:
            raise ValueError("Sentinel is not awaiting simulated ATC")
        if decision.decision == ATCDecisionType.REJECT:
            return SentinelDecision(
                decision_id=uuid4(),
                scenario_run_id=decision.scenario_run_id,
                incident_id=decision.incident_id,
                sentinel_state=SentinelState.AWAITING_ATC,
                action_type=SimulatorActionType.NO_OP,
                authorization_source=AuthorizationSource.SIMULATED_ATC,
                reason="Simulated ATC rejected the requested action; no action executed.",
                evidence_event_ids=self._incident.evidence_event_ids,
                executed_at=decision.issued_at,
                result=DecisionResult.REJECTED,
            )
        if decision.requested_action == SimulatorActionType.NO_OP:
            raise ValueError("APPROVE must request a non-NO_OP symbolic action")
        self._state = SentinelState.SIM_ACTION_RUNNING
        return SentinelDecision(
            decision_id=uuid4(),
            scenario_run_id=decision.scenario_run_id,
            incident_id=decision.incident_id,
            sentinel_state=self._state,
            action_type=decision.requested_action,
            authorization_source=AuthorizationSource.SIMULATED_ATC,
            reason="Fresh simulated ATC APPROVE matched the active run and incident.",
            evidence_event_ids=self._incident.evidence_event_ids,
            executed_at=decision.issued_at,
            result=DecisionResult.APPROVED,
        )

    def set_atc_link(self, scenario_run_id: UUID, connected: bool) -> None:
        if scenario_run_id != self._run_id:
            raise ValueError("Sentinel rejected stale scenario_run_id")
        self._atc_connected = connected
        if not connected and self._state == SentinelState.AWAITING_ATC:
            self._state = SentinelState.STANDBY

    def complete_action(self) -> None:
        if self._state != SentinelState.SIM_ACTION_RUNNING:
            raise ValueError("no simulator action is running")
        self._state = SentinelState.COMPLETED
