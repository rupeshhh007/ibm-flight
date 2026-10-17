"""SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE."""

from copy import deepcopy
from uuid import UUID

import pytest

from app.contracts.enums import ATCDecisionType, DecisionResult, SentinelState
from app.contracts.models import ATCDecision, GuardianIncident
from app.modules.sentinel import DeterministicSentinelAgent


def test_corrupt_caller_data_and_outputs_cannot_change_retained_authorization(
    atc_incident: GuardianIncident, atc_command: ATCDecision,
) -> None:
    original = atc_incident.model_copy(deep=True)
    agent = DeterministicSentinelAgent()
    agent.reset(original.scenario_run_id, True)
    pending = agent.on_incident(atc_incident, original.created_at)
    rejection = atc_command.model_copy(update={"command_id": UUID(int=601), "decision": ATCDecisionType.REJECT})
    rejected = agent.decide(rejection)
    before = deepcopy(vars(agent))
    atc_incident.incident_id = UUID(int=699)
    atc_incident.scenario_run_id = UUID(int=698)
    atc_incident.evidence_event_ids[:] = [UUID(int=697)]
    pending.evidence_event_ids.clear()
    pending.result = DecisionResult.APPROVED
    rejected.incident_id = UUID(int=696)
    rejected.evidence_event_ids.clear()
    rejection.operator_id = "changed-after-consumption"
    assert vars(agent) == before
    with pytest.raises(ValueError, match="command_id conflict"):
        agent.decide(rejection)
    with pytest.raises(ValueError, match="scenario_run_id"):
        agent.on_incident(atc_incident, original.created_at)
    assert vars(agent) == before
    authorized = agent.decide(atc_command)
    assert authorized.incident_id == original.incident_id
    assert authorized.scenario_run_id == original.scenario_run_id
    assert authorized.evidence_event_ids == original.evidence_event_ids
    before = deepcopy(vars(agent))
    authorized.scenario_run_id = UUID(int=695)
    authorized.sentinel_state = SentinelState.STANDBY
    authorized.evidence_event_ids.clear()
    atc_command.command_id = UUID(int=694)
    assert vars(agent) == before


def test_corrupted_incidents_do_not_replace_retained_data_or_pending_identity(
    waiting_agent: DeterministicSentinelAgent, atc_incident: GuardianIncident, atc_command: ATCDecision,
) -> None:
    for field, value, message in (
        ("evidence_event_ids", [], "evidence_event_ids"),
        ("incident_id", "not-a-uuid", "incident_id"),
        ("guardian_state", "UNRECOGNIZED", "guardian_state"),
        ("created_at", atc_incident.created_at.replace(tzinfo=None), "timezone-aware"),
    ):
        before = deepcopy(vars(waiting_agent))
        with pytest.raises(ValueError, match=message):
            waiting_agent.on_incident(atc_incident.model_copy(update={field: value}), atc_command.issued_at)
        assert vars(waiting_agent) == before
    assert waiting_agent.decide(atc_command).result == DecisionResult.APPROVED


def test_false_like_link_inputs_cannot_erase_consumption_or_authorization(
    waiting_agent: DeterministicSentinelAgent, atc_incident: GuardianIncident, atc_command: ATCDecision,
) -> None:
    waiting_agent.decide(atc_command)
    for value in ("false", "true", 0, 1, None):
        before = deepcopy(vars(waiting_agent))
        with pytest.raises(ValueError, match="connected must be a bool"):
            waiting_agent.set_atc_link(atc_incident.scenario_run_id, value)  # type: ignore[arg-type]
        assert vars(waiting_agent) == before
        with pytest.raises(ValueError, match="replayed command_id"):
            waiting_agent.decide(atc_command)
        assert vars(waiting_agent) == before
