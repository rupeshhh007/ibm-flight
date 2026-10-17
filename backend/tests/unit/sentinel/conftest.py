"""SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.contracts.enums import ATCDecisionType, GuardianState, IncidentSeverity, IncidentType, SimulatorActionType
from app.contracts.models import ATCDecision, GuardianIncident
from app.modules.sentinel import DeterministicSentinelAgent


@pytest.fixture
def atc_incident() -> GuardianIncident:
    return GuardianIncident(
        incident_id=UUID(int=203), scenario_run_id=UUID(int=201),
        incident_type=IncidentType.DUAL_PILOT_UNRESPONSIVE,
        severity=IncidentSeverity.CRITICAL, guardian_state=GuardianState.ESCALATED,
        evidence_event_ids=[UUID(int=204), UUID(int=205)],
        explanation="Synthetic fixture; upstream verifies evidence.",
        acknowledgement_required=True,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def atc_command(atc_incident: GuardianIncident) -> ATCDecision:
    return ATCDecision(
        command_id=UUID(int=206), scenario_run_id=atc_incident.scenario_run_id,
        incident_id=atc_incident.incident_id, decision=ATCDecisionType.APPROVE,
        requested_action=SimulatorActionType.SIM_STABILIZE, operator_id="fictional-atc",
        issued_at=atc_incident.created_at + timedelta(seconds=2),
    )


@pytest.fixture
def waiting_agent(atc_incident: GuardianIncident) -> DeterministicSentinelAgent:
    agent = DeterministicSentinelAgent()
    agent.reset(atc_incident.scenario_run_id, True)
    agent.on_incident(atc_incident, atc_incident.created_at + timedelta(seconds=1))
    return agent
