"""SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE."""

from copy import deepcopy
from datetime import timedelta, timezone
from uuid import UUID

import pytest

from app.contracts.enums import ATCDecisionType, DecisionResult, SentinelState, SimulatorActionType
from app.contracts.models import ATCDecision, GuardianIncident
from app.modules.sentinel import DeterministicSentinelAgent


@pytest.mark.parametrize("choice", list(ATCDecisionType))
@pytest.mark.parametrize("completed", [False, True])
def test_consumed_command_replay_is_rejected_without_mutation(
    waiting_agent: DeterministicSentinelAgent, atc_command: ATCDecision,
    choice: ATCDecisionType, completed: bool,
) -> None:
    command = atc_command.model_copy(update={"decision": choice})
    waiting_agent.decide(command)
    if completed:
        if choice == ATCDecisionType.REJECT:
            waiting_agent.decide(atc_command.model_copy(update={"command_id": UUID(int=210)}))
        waiting_agent.complete_action()
    before = deepcopy(vars(waiting_agent))
    with pytest.raises(ValueError, match="replayed command_id"):
        waiting_agent.decide(command)
    assert vars(waiting_agent) == before


@pytest.mark.parametrize("choice", list(ATCDecisionType))
@pytest.mark.parametrize("field", [
    "incident_id", "scenario_run_id", "requested_action", "decision", "operator_id", "issued_at",
])
def test_consumed_id_conflicts_on_every_changed_canonical_field(
    waiting_agent: DeterministicSentinelAgent, atc_command: ATCDecision,
    choice: ATCDecisionType, field: str,
) -> None:
    command = atc_command.model_copy(update={"decision": choice})
    waiting_agent.decide(command)
    replacements = {
        "incident_id": UUID(int=299), "scenario_run_id": UUID(int=299),
        "requested_action": SimulatorActionType.SIM_HOLD_STATE,
        "decision": ATCDecisionType.REJECT if choice == ATCDecisionType.APPROVE else ATCDecisionType.APPROVE,
        "operator_id": "another-operator", "issued_at": command.issued_at + timedelta(microseconds=1),
    }
    before = deepcopy(vars(waiting_agent))
    with pytest.raises(ValueError, match="command_id conflict"):
        waiting_agent.decide(command.model_copy(update={field: replacements[field]}))
    assert vars(waiting_agent) == before


def test_timezone_equivalent_content_is_a_replay_not_a_conflict(
    waiting_agent: DeterministicSentinelAgent, atc_command: ATCDecision,
) -> None:
    waiting_agent.decide(atc_command)
    equivalent = atc_command.model_copy(update={
        "issued_at": atc_command.issued_at.astimezone(timezone(timedelta(hours=5, minutes=30))),
    })
    before = deepcopy(vars(waiting_agent))
    with pytest.raises(ValueError, match="replayed command_id"):
        waiting_agent.decide(equivalent)
    assert vars(waiting_agent) == before


def test_registry_owns_immutable_content_independent_of_caller_mutation(
    waiting_agent: DeterministicSentinelAgent, atc_command: ATCDecision,
) -> None:
    original = atc_command.model_copy(deep=True)
    waiting_agent.decide(atc_command)
    before = deepcopy(vars(waiting_agent))
    atc_command.operator_id = "changed-after-consumption"
    with pytest.raises(ValueError, match="command_id conflict"):
        waiting_agent.decide(atc_command)
    with pytest.raises(ValueError, match="replayed command_id"):
        waiting_agent.decide(original)
    assert vars(waiting_agent) == before


def test_fresh_rejections_are_consumed_without_blocking_fresh_approval(
    waiting_agent: DeterministicSentinelAgent, atc_command: ATCDecision,
) -> None:
    for number in (210, 211, 212):
        rejection = atc_command.model_copy(update={"command_id": UUID(int=number), "decision": ATCDecisionType.REJECT})
        assert waiting_agent.decide(rejection).result == DecisionResult.REJECTED
        assert waiting_agent.state == SentinelState.AWAITING_ATC
        before = deepcopy(vars(waiting_agent))
        with pytest.raises(ValueError, match="replayed command_id"):
            waiting_agent.decide(rejection)
        assert vars(waiting_agent) == before
    assert waiting_agent.decide(atc_command).result == DecisionResult.APPROVED


@pytest.mark.parametrize("choice", list(ATCDecisionType))
def test_registry_survives_link_cycles_and_redelivery(
    waiting_agent: DeterministicSentinelAgent, atc_incident: GuardianIncident,
    atc_command: ATCDecision, choice: ATCDecisionType,
) -> None:
    command = atc_command.model_copy(update={"decision": choice})
    waiting_agent.decide(command)
    registry = deepcopy(waiting_agent._consumed_commands)
    for connected in (False, False, True, True):
        waiting_agent.set_atc_link(atc_incident.scenario_run_id, connected)
        before = deepcopy(vars(waiting_agent))
        with pytest.raises(ValueError, match="replayed command_id"):
            waiting_agent.decide(command)
        assert vars(waiting_agent) == before
        assert waiting_agent._consumed_commands == registry
    if choice == ATCDecisionType.REJECT:
        # First observation remains t=1 even though reconnect redelivery is at t=10.
        waiting_agent.on_incident(atc_incident, atc_incident.created_at + timedelta(seconds=10))
        assert waiting_agent.decide(atc_command.model_copy(update={"command_id": UUID(int=213)})).result == DecisionResult.APPROVED
    else:
        with pytest.raises(ValueError, match="not awaiting"):
            waiting_agent.decide(command.model_copy(update={"command_id": UUID(int=213)}))


@pytest.mark.parametrize("completed", [False, True])
def test_new_id_cannot_reauthorize_running_or_completed(
    waiting_agent: DeterministicSentinelAgent, atc_command: ATCDecision, completed: bool,
) -> None:
    waiting_agent.decide(atc_command)
    if completed:
        waiting_agent.complete_action()
    before = deepcopy(vars(waiting_agent))
    with pytest.raises(ValueError, match="not awaiting"):
        waiting_agent.decide(atc_command.model_copy(update={"command_id": UUID(int=214)}))
    assert vars(waiting_agent) == before


@pytest.mark.parametrize("completed", [False, True])
def test_reset_clears_registry_and_first_observation_for_new_run(
    waiting_agent: DeterministicSentinelAgent, atc_incident: GuardianIncident,
    atc_command: ATCDecision, completed: bool,
) -> None:
    waiting_agent.decide(atc_command)
    if completed:
        waiting_agent.complete_action()
    new_run = UUID(int=202)
    waiting_agent.reset(new_run, True)
    assert waiting_agent._consumed_commands == {}
    assert waiting_agent._incident_observed_at is None
    before = deepcopy(vars(waiting_agent))
    with pytest.raises(ValueError, match="scenario_run_id"):
        waiting_agent.decide(atc_command)
    assert vars(waiting_agent) == before
    # Local registry scope resets; orchestration's durable command log is separate.
    current = atc_incident.model_copy(update={"scenario_run_id": new_run})
    waiting_agent.on_incident(current, current.created_at)
    current_command = atc_command.model_copy(update={"scenario_run_id": new_run, "issued_at": current.created_at})
    assert waiting_agent.decide(current_command).result == DecisionResult.APPROVED


def test_invalid_reset_preserves_consumed_registry(
    waiting_agent: DeterministicSentinelAgent, atc_command: ATCDecision,
) -> None:
    rejection = atc_command.model_copy(update={"decision": ATCDecisionType.REJECT})
    waiting_agent.decide(rejection)
    before = deepcopy(vars(waiting_agent))
    with pytest.raises(ValueError, match="atc_connected must be a bool"):
        waiting_agent.reset(UUID(int=202), 1)  # type: ignore[arg-type]
    assert vars(waiting_agent) == before
    with pytest.raises(ValueError, match="replayed command_id"):
        waiting_agent.decide(rejection)
