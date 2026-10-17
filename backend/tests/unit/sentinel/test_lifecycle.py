"""SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID

import pytest

from app.contracts.enums import (
    ATCDecisionType,
    AuthorizationSource,
    DecisionResult,
    GuardianState,
    IncidentSeverity,
    IncidentType,
    SentinelState,
    SimulatorActionType,
)
from app.contracts.interfaces import SentinelAgent
from app.contracts.models import ATCDecision, GuardianIncident, SentinelDecision
from app.modules.sentinel import DeterministicSentinelAgent


RUN = UUID(int=101)
NEW_RUN = UUID(int=102)
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
STAGES = ("initial", "standby", "waiting", "disconnected", "running", "completed")
INVALID_FLAGS = ("false", "true", 0, 1, None, [], {})


@pytest.fixture
def incident() -> GuardianIncident:
    return GuardianIncident(
        incident_id=UUID(int=103),
        scenario_run_id=RUN,
        incident_type=IncidentType.DUAL_PILOT_UNRESPONSIVE,
        severity=IncidentSeverity.CRITICAL,
        guardian_state=GuardianState.ESCALATED,
        evidence_event_ids=[UUID(int=104), UUID(int=105)],
        explanation="Fixed synthetic incident; evidence provenance belongs upstream.",
        acknowledgement_required=True,
        created_at=NOW,
    )


@pytest.fixture
def approval(incident: GuardianIncident) -> ATCDecision:
    return ATCDecision(
        command_id=UUID(int=106),
        scenario_run_id=RUN,
        incident_id=incident.incident_id,
        decision=ATCDecisionType.APPROVE,
        requested_action=SimulatorActionType.SIM_STABILIZE,
        operator_id="fictional-atc",
        issued_at=NOW + timedelta(seconds=1),
    )


def at_stage(
    stage: str, incident: GuardianIncident, approval: ATCDecision
) -> DeterministicSentinelAgent:
    agent = DeterministicSentinelAgent()
    if stage == "initial":
        return agent
    agent.reset(RUN, stage != "disconnected")
    if stage in {"waiting", "disconnected", "running", "completed"}:
        agent.on_incident(incident, NOW)
    if stage in {"running", "completed"}:
        agent.decide(approval)
    if stage == "completed":
        agent.complete_action()
    return agent


def assert_no_action(decision: SentinelDecision) -> None:
    assert decision.result == DecisionResult.PENDING
    assert decision.action_type == SimulatorActionType.NO_OP
    assert decision.authorization_source == AuthorizationSource.NONE
    assert decision.sentinel_state not in {
        SentinelState.LOCAL_FALLBACK, SentinelState.SIM_ACTION_RUNNING, SentinelState.COMPLETED
    }


@pytest.mark.parametrize("stage", STAGES[1:])
def test_link_cycle_preserves_incident_and_authorization(
    stage: str, incident: GuardianIncident, approval: ATCDecision
) -> None:
    agent = at_stage(stage, incident, approval)
    original_incident = deepcopy(agent._incident)
    original_authorization = deepcopy(agent._authorization)
    expected = agent.state if stage in {"running", "completed"} else SentinelState.STANDBY

    for connected in (False, False, True, True, False, True):
        assert agent.set_atc_link(RUN, connected) is None
        assert agent.state == expected
        assert agent._incident == original_incident
        assert agent._authorization == original_authorization
        before = deepcopy(vars(agent))
        with pytest.raises(ValueError, match="not awaiting|no active incident"):
            agent.decide(approval)
        assert vars(agent) == before

    if stage in {"running", "completed"}:
        with pytest.raises(ValueError, match="cannot reopen"):
            agent.on_incident(incident, NOW)
        assert agent._authorization == original_authorization
    elif original_incident is not None:
        pending = agent.on_incident(incident, NOW + timedelta(seconds=2))
        assert_no_action(pending)
        assert agent.state == SentinelState.AWAITING_ATC
        assert agent.decide(approval).result == DecisionResult.APPROVED


@pytest.mark.parametrize("connected", [True, False])
def test_same_link_is_idempotent_for_pending_decision(
    incident: GuardianIncident, connected: bool
) -> None:
    agent = DeterministicSentinelAgent()
    agent.reset(RUN, connected)
    pending = agent.on_incident(incident, NOW)
    before = deepcopy(vars(agent))
    for _ in range(3):
        agent.set_atc_link(RUN, connected)
        assert vars(agent) == before
        assert agent.on_incident(incident, NOW + timedelta(seconds=1)) == pending


def test_genuine_link_changes_invalidate_pending_without_replacing_incident(
    incident: GuardianIncident, approval: ATCDecision
) -> None:
    agent = at_stage("standby", incident, approval)
    original = incident.model_copy(deep=True)
    first = agent.on_incident(incident, NOW)
    incident.evidence_event_ids.clear()
    first.evidence_event_ids.clear()
    agent.set_atc_link(RUN, False)
    assert agent._pending is None
    offline = agent.on_incident(original, NOW + timedelta(seconds=1))
    assert_no_action(offline)
    assert offline.decision_id != first.decision_id
    agent.set_atc_link(RUN, True)
    assert agent.state == SentinelState.STANDBY
    assert agent._pending is None
    before = deepcopy(vars(agent))
    with pytest.raises(ValueError, match="not awaiting"):
        agent.decide(approval)
    assert vars(agent) == before
    pending = agent.on_incident(original, NOW + timedelta(seconds=2))
    assert_no_action(pending)
    assert pending.decision_id not in {first.decision_id, offline.decision_id}
    assert pending.incident_id == original.incident_id
    assert pending.evidence_event_ids == original.evidence_event_ids
    pending.evidence_event_ids.clear()
    assert agent.on_incident(original, NOW).evidence_event_ids == original.evidence_event_ids


@pytest.mark.parametrize("stage", STAGES[1:])
@pytest.mark.parametrize("connected", INVALID_FLAGS)
def test_non_boolean_link_input_is_rejected_without_mutation(
    stage: str, connected: object, incident: GuardianIncident, approval: ATCDecision
) -> None:
    agent = at_stage(stage, incident, approval)
    before = deepcopy(vars(agent))
    with pytest.raises(ValueError, match="connected must be a bool"):
        agent.set_atc_link(RUN, cast(bool, connected))
    assert vars(agent) == before


@pytest.mark.parametrize("stage", STAGES)
def test_stale_link_input_does_not_mutate(
    stage: str, incident: GuardianIncident, approval: ATCDecision
) -> None:
    agent = at_stage(stage, incident, approval)
    before = deepcopy(vars(agent))
    with pytest.raises(ValueError, match="scenario_run_id"):
        agent.set_atc_link(NEW_RUN, False)
    assert vars(agent) == before


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize(
    ("run_id", "connected", "message"),
    [(value, False, "scenario_run_id must be a UUID") for value in (str(NEW_RUN), None, 1, False)]
    + [(NEW_RUN, value, "atc_connected must be a bool") for value in INVALID_FLAGS],
)
def test_invalid_reset_is_atomic(
    stage: str,
    run_id: object,
    connected: object,
    message: str,
    incident: GuardianIncident,
    approval: ATCDecision,
) -> None:
    agent = at_stage(stage, incident, approval)
    before = deepcopy(vars(agent))
    with pytest.raises(ValueError, match=message):
        agent.reset(cast(UUID, run_id), cast(bool, connected))
    assert vars(agent) == before


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("connected", [True, False])
def test_reset_clears_lifecycle_and_rejects_all_old_run_inputs(
    stage: str, connected: bool, incident: GuardianIncident, approval: ATCDecision
) -> None:
    agent = at_stage(stage, incident, approval)
    assert agent.reset(NEW_RUN, connected) is None
    assert isinstance(agent, SentinelAgent)
    assert agent.state == SentinelState.STANDBY
    assert agent._incident is None
    assert agent._pending is None
    assert agent._authorization is None
    before = deepcopy(vars(agent))
    for operation in (
        lambda: agent.on_incident(incident, NOW),
        lambda: agent.decide(approval),
        lambda: agent.set_atc_link(RUN, not connected),
        agent.complete_action,
    ):
        with pytest.raises(ValueError):
            operation()
        assert vars(agent) == before

    # Reuse the incident ID deliberately: the run boundary must still reject old approvals.
    current = incident.model_copy(update={"scenario_run_id": NEW_RUN})
    pending = agent.on_incident(current, NOW)
    assert_no_action(pending)
    assert agent.state == (SentinelState.AWAITING_ATC if connected else SentinelState.STANDBY)
    before = deepcopy(vars(agent))
    with pytest.raises(ValueError, match="scenario_run_id"):
        agent.decide(approval)
    assert vars(agent) == before
    if connected:
        current_approval = approval.model_copy(update={"scenario_run_id": NEW_RUN})
        assert agent.decide(current_approval).result == DecisionResult.APPROVED


@pytest.mark.parametrize("stage", STAGES)
def test_completion_only_from_running_and_never_creates_another_operation(
    stage: str, incident: GuardianIncident, approval: ATCDecision
) -> None:
    agent = at_stage(stage, incident, approval)
    before = deepcopy(vars(agent))
    if stage != "running":
        with pytest.raises(ValueError, match="no simulator action is running"):
            agent.complete_action()
        assert vars(agent) == before
        return

    # Completion only changes state; it emits no decision and retains authorization identity.
    agent.set_atc_link(RUN, False)
    before = deepcopy(vars(agent))
    assert agent.complete_action() is None
    assert vars(agent) == {**before, "_state": SentinelState.COMPLETED}
    for connected in (False, True, True, False):
        agent.set_atc_link(RUN, connected)
        before = deepcopy(vars(agent))
        for operation in (
            agent.complete_action,
            lambda: agent.decide(approval),
            lambda: agent.on_incident(incident, NOW),
        ):
            with pytest.raises(ValueError):
                operation()
            assert vars(agent) == before
