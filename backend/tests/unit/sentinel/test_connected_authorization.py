"""SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE."""

from copy import deepcopy
from datetime import timedelta, timezone
from typing import cast
from uuid import UUID

import pytest

from app.contracts.enums import ATCDecisionType, AuthorizationSource, DecisionResult, SentinelState, SimulatorActionType
from app.contracts.interfaces import SentinelAgent
from app.contracts.models import ATCDecision, GuardianIncident, SentinelDecision
from app.modules.sentinel import DeterministicSentinelAgent


@pytest.mark.parametrize("action", [action for action in SimulatorActionType if action != SimulatorActionType.NO_OP])
def test_canonical_non_no_op_actions_are_authorized_once(
    waiting_agent: DeterministicSentinelAgent, atc_command: ATCDecision,
    atc_incident: GuardianIncident, action: SimulatorActionType,
) -> None:
    atc_command.requested_action = action
    decision = waiting_agent.decide(atc_command)
    assert isinstance(waiting_agent, SentinelAgent)
    assert SentinelDecision.model_validate_json(decision.model_dump_json()) == decision
    assert decision.action_type == action
    assert decision.result == DecisionResult.APPROVED
    assert decision.authorization_source == AuthorizationSource.SIMULATED_ATC
    assert decision.sentinel_state == waiting_agent.state == SentinelState.SIM_ACTION_RUNNING
    assert decision.incident_id == atc_incident.incident_id
    assert decision.scenario_run_id == atc_incident.scenario_run_id
    assert decision.evidence_event_ids == atc_incident.evidence_event_ids
    assert decision.executed_at == atc_command.issued_at
    before = deepcopy(vars(waiting_agent))
    decision.evidence_event_ids.clear()
    decision.decision_id = UUID(int=999)
    atc_command.operator_id = "mutated"
    assert vars(waiting_agent) == before


@pytest.mark.parametrize("action", list(SimulatorActionType))
def test_reject_remains_pending_and_allows_fresh_approval(
    waiting_agent: DeterministicSentinelAgent, atc_command: ATCDecision, action: SimulatorActionType,
) -> None:
    rejection = atc_command.model_copy(update={"decision": ATCDecisionType.REJECT, "requested_action": action})
    rejected = waiting_agent.decide(rejection)
    assert rejected.result == DecisionResult.REJECTED
    assert rejected.action_type == SimulatorActionType.NO_OP
    assert rejected.authorization_source == AuthorizationSource.SIMULATED_ATC
    assert waiting_agent.state == SentinelState.AWAITING_ATC
    assert waiting_agent._authorization is None
    assert waiting_agent.decide(atc_command.model_copy(update={"command_id": UUID(int=207)})).result == DecisionResult.APPROVED


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [("scenario_run_id", UUID(int=299), "scenario_run_id"),
     ("incident_id", UUID(int=299), "incident_id"),
     ("requested_action", SimulatorActionType.NO_OP, "non-NO_OP")],
)
def test_invalid_context_does_not_consume_id(
    waiting_agent: DeterministicSentinelAgent, atc_command: ATCDecision,
    field: str, value: object, message: str,
) -> None:
    before = deepcopy(vars(waiting_agent))
    with pytest.raises(ValueError, match=message):
        waiting_agent.decide(atc_command.model_copy(update={field: value}))
    assert vars(waiting_agent) == before
    assert waiting_agent.decide(atc_command).result == DecisionResult.APPROVED


@pytest.mark.parametrize("stage", ["initial", "standby", "disconnected", "reconnected", "running", "completed"])
def test_approval_requires_waiting_connected_lifecycle(
    atc_incident: GuardianIncident, atc_command: ATCDecision, stage: str,
) -> None:
    agent = DeterministicSentinelAgent()
    if stage != "initial":
        agent.reset(atc_incident.scenario_run_id, True)
    if stage in {"disconnected", "reconnected", "running", "completed"}:
        agent.on_incident(atc_incident, atc_incident.created_at)
    if stage in {"disconnected", "reconnected"}:
        agent.set_atc_link(atc_incident.scenario_run_id, False)
    if stage == "reconnected":
        agent.set_atc_link(atc_incident.scenario_run_id, True)
    if stage in {"running", "completed"}:
        agent.decide(atc_command)
    if stage == "completed":
        agent.complete_action()
    before = deepcopy(vars(agent))
    message = "scenario_run_id" if stage == "initial" else "no active incident|not awaiting"
    with pytest.raises(ValueError, match=message):
        agent.decide(atc_command.model_copy(update={"command_id": UUID(int=208)}))
    assert vars(agent) == before


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [("decision", "NOT_APPROVAL", "decision"),
     ("requested_action", "REAL_ACTION", "requested_action"),
     ("command_id", "invalid", "command_id"),
     ("issued_at", None, "issued_at"),
     ("issued_at", "invalid", "issued_at")],
)
def test_mutated_canonical_model_is_revalidated_without_consumption(
    waiting_agent: DeterministicSentinelAgent, atc_command: ATCDecision,
    field: str, value: object, message: str,
) -> None:
    invalid = atc_command.model_copy(update={field: value})
    before = deepcopy(vars(waiting_agent))
    with pytest.raises(ValueError, match=message):
        waiting_agent.decide(invalid)
    assert vars(waiting_agent) == before
    assert waiting_agent.decide(atc_command).result == DecisionResult.APPROVED


def test_noncanonical_command_is_rejected(waiting_agent: DeterministicSentinelAgent) -> None:
    before = deepcopy(vars(waiting_agent))
    with pytest.raises(ValueError, match="canonical ATCDecision"):
        waiting_agent.decide(cast(ATCDecision, {}))
    assert vars(waiting_agent) == before


@pytest.mark.parametrize("choice", list(ATCDecisionType))
@pytest.mark.parametrize("seconds", [-1, 0, 1, 2])
def test_event_time_thresholds(
    waiting_agent: DeterministicSentinelAgent, atc_incident: GuardianIncident,
    atc_command: ATCDecision, seconds: int, choice: ATCDecisionType,
) -> None:
    command = atc_command.model_copy(update={
        "decision": choice, "issued_at": atc_incident.created_at + timedelta(seconds=seconds),
    })
    before = deepcopy(vars(waiting_agent))
    if seconds < 1:
        with pytest.raises(ValueError, match="cannot precede"):
            waiting_agent.decide(command)
        assert vars(waiting_agent) == before
        assert waiting_agent.decide(atc_command).result == DecisionResult.APPROVED
    else:
        expected = DecisionResult.APPROVED if choice == ATCDecisionType.APPROVE else DecisionResult.REJECTED
        assert waiting_agent.decide(command).result == expected


def test_equality_at_creation_and_observation_is_permitted(
    atc_incident: GuardianIncident, atc_command: ATCDecision,
) -> None:
    agent = DeterministicSentinelAgent()
    agent.reset(atc_incident.scenario_run_id, True)
    agent.on_incident(atc_incident, atc_incident.created_at)
    command = atc_command.model_copy(update={"issued_at": atc_incident.created_at})
    assert agent.decide(command).result == DecisionResult.APPROVED


def test_timezone_offsets_compare_instants_and_normalize_output(
    atc_incident: GuardianIncident, atc_command: ATCDecision,
) -> None:
    agent = DeterministicSentinelAgent()
    agent.reset(atc_incident.scenario_run_id, True)
    observed = atc_incident.created_at + timedelta(seconds=1)
    agent.on_incident(atc_incident, observed.astimezone(timezone(timedelta(hours=5, minutes=30))))
    command = atc_command.model_copy(update={"issued_at": observed.astimezone(timezone(timedelta(hours=-7)))})
    assert agent.decide(command).executed_at == observed


def test_naive_command_time_is_rejected_without_mutation(
    waiting_agent: DeterministicSentinelAgent, atc_command: ATCDecision,
) -> None:
    before = deepcopy(vars(waiting_agent))
    with pytest.raises(ValueError, match="timezone-aware"):
        waiting_agent.decide(atc_command.model_copy(update={"issued_at": atc_command.issued_at.replace(tzinfo=None)}))
    assert vars(waiting_agent) == before


@pytest.mark.parametrize("redelivery", [False, True])
@pytest.mark.parametrize("invalid", ["naive", "before_creation", "not_datetime"])
def test_invalid_observation_time_is_atomic_even_on_cached_redelivery(
    atc_incident: GuardianIncident, redelivery: bool, invalid: str,
) -> None:
    agent = DeterministicSentinelAgent()
    agent.reset(atc_incident.scenario_run_id, True)
    if redelivery:
        agent.on_incident(atc_incident, atc_incident.created_at)
    value = {
        "naive": atc_incident.created_at.replace(tzinfo=None),
        "before_creation": atc_incident.created_at - timedelta(microseconds=1),
        "not_datetime": "2026-01-01",
    }[invalid]
    before = deepcopy(vars(agent))
    with pytest.raises(ValueError, match="timezone-aware|cannot precede"):
        agent.on_incident(atc_incident, value)  # type: ignore[arg-type]
    assert vars(agent) == before


@pytest.mark.parametrize("choice", list(ATCDecisionType))
def test_output_construction_failure_does_not_partially_consume(
    waiting_agent: DeterministicSentinelAgent, atc_command: ATCDecision, monkeypatch: pytest.MonkeyPatch,
    choice: ATCDecisionType,
) -> None:
    def fail_output(**kwargs: object) -> SentinelDecision:
        raise ValueError("output validation failed")

    before = deepcopy(vars(waiting_agent))
    command = atc_command.model_copy(update={"decision": choice})
    with monkeypatch.context() as patch:
        patch.setattr("app.modules.sentinel.deterministic.SentinelDecision", fail_output)
        with pytest.raises(ValueError, match="output validation failed"):
            waiting_agent.decide(command)
    assert vars(waiting_agent) == before
    assert waiting_agent.decide(atc_command).result == DecisionResult.APPROVED


def test_invalid_attempt_preserves_existing_registry_and_does_not_poison_new_id(
    waiting_agent: DeterministicSentinelAgent, atc_command: ATCDecision,
) -> None:
    rejection = atc_command.model_copy(update={"decision": ATCDecisionType.REJECT})
    waiting_agent.decide(rejection)
    fresh = atc_command.model_copy(update={"command_id": UUID(int=220)})
    invalid = fresh.model_copy(update={"issued_at": atc_command.issued_at - timedelta(days=1)})
    before = deepcopy(vars(waiting_agent))
    with pytest.raises(ValueError, match="cannot precede incident creation"):
        waiting_agent.decide(invalid)
    assert vars(waiting_agent) == before
    assert waiting_agent.decide(fresh).result == DecisionResult.APPROVED


def test_disconnected_attempt_is_unconsumed_and_can_be_retried_after_valid_redelivery(
    waiting_agent: DeterministicSentinelAgent, atc_incident: GuardianIncident, atc_command: ATCDecision,
) -> None:
    waiting_agent.set_atc_link(atc_incident.scenario_run_id, False)
    before = deepcopy(vars(waiting_agent))
    with pytest.raises(ValueError, match="not awaiting"):
        waiting_agent.decide(atc_command)
    assert vars(waiting_agent) == before
    waiting_agent.set_atc_link(atc_incident.scenario_run_id, True)
    waiting_agent.on_incident(atc_incident, atc_command.issued_at)
    assert waiting_agent.decide(atc_command).result == DecisionResult.APPROVED
