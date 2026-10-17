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
from app.modules.sentinel import DeterministicSentinelAgent, MockSentinelAgent


RUN = UUID(int=1)
NEW_RUN = UUID(int=2)
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def incident() -> GuardianIncident:
    return GuardianIncident(
        incident_id=UUID(int=3),
        scenario_run_id=RUN,
        incident_type=IncidentType.DUAL_PILOT_UNRESPONSIVE,
        severity=IncidentSeverity.CRITICAL,
        guardian_state=GuardianState.ESCALATED,
        evidence_event_ids=[UUID(int=4), UUID(int=5)],
        explanation="Synthetic dual-pilot escalation fixture; provenance is upstream.",
        acknowledgement_required=True,
        created_at=NOW,
    )


@pytest.fixture
def agent() -> DeterministicSentinelAgent:
    agent = DeterministicSentinelAgent()
    agent.reset(RUN, True)
    return agent


@pytest.fixture
def approval(incident: GuardianIncident) -> ATCDecision:
    return ATCDecision(
        command_id=UUID(int=6),
        scenario_run_id=RUN,
        incident_id=incident.incident_id,
        decision=ATCDecisionType.APPROVE,
        requested_action=SimulatorActionType.SIM_STABILIZE,
        operator_id="fictional-atc",
        issued_at=NOW + timedelta(seconds=1),
    )


def assert_pending(decision: SentinelDecision, incident: GuardianIncident) -> None:
    assert type(decision) is SentinelDecision
    assert SentinelDecision.model_validate_json(decision.model_dump_json()) == decision
    assert decision.scenario_run_id == incident.scenario_run_id
    assert decision.incident_id == incident.incident_id
    assert decision.evidence_event_ids == incident.evidence_event_ids
    assert decision.action_type == SimulatorActionType.NO_OP
    assert decision.authorization_source == AuthorizationSource.NONE
    assert decision.result == DecisionResult.PENDING
    assert decision.result not in {DecisionResult.APPROVED, DecisionResult.EXECUTED}


def test_initial_state_and_runtime_protocol(incident: GuardianIncident) -> None:
    agent = DeterministicSentinelAgent()
    assert agent.state == SentinelState.STANDBY
    assert isinstance(agent, SentinelAgent)
    before = deepcopy(vars(agent))
    with pytest.raises(ValueError, match="scenario_run_id"):
        agent.on_incident(incident, NOW)
    assert vars(agent) == before


def test_original_mock_remains_exported() -> None:
    assert isinstance(MockSentinelAgent(), SentinelAgent)
    assert MockSentinelAgent().state == SentinelState.STANDBY


@pytest.mark.parametrize("connected", [True, False])
def test_incident_is_pending_only(
    agent: DeterministicSentinelAgent, incident: GuardianIncident, connected: bool
) -> None:
    agent.reset(RUN, connected)
    decision = agent.on_incident(incident, NOW)
    assert_pending(decision, incident)
    expected = SentinelState.AWAITING_ATC if connected else SentinelState.STANDBY
    assert decision.sentinel_state == agent.state == expected
    assert decision.executed_at == NOW
    assert decision.reason
    with pytest.raises(ValueError, match="no simulator action"):
        agent.complete_action()


@pytest.mark.parametrize("connected", [True, False])
def test_identical_pending_redelivery_keeps_identity_and_timestamp(
    agent: DeterministicSentinelAgent, incident: GuardianIncident, connected: bool
) -> None:
    agent.reset(RUN, connected)
    first = agent.on_incident(incident, NOW)
    again = agent.on_incident(incident.model_copy(deep=True), NOW + timedelta(seconds=1))
    assert again == first
    assert again is not first
    assert_pending(again, incident)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("scenario_run_id", NEW_RUN, "scenario_run_id"),
        ("guardian_state", GuardianState.AWAITING_ACK, "ESCALATED"),
        ("incident_type", IncidentType.PILOT_RESPONSE_REQUIRED, "DUAL_PILOT"),
    ],
)
@pytest.mark.parametrize("pending", [False, True])
def test_invalid_incident_does_not_mutate(
    agent: DeterministicSentinelAgent,
    incident: GuardianIncident,
    field: str,
    value: object,
    message: str,
    pending: bool,
) -> None:
    if pending:
        agent.on_incident(incident, NOW)
    invalid = GuardianIncident.model_validate({**incident.model_dump(), field: value})
    before = deepcopy(vars(agent))
    with pytest.raises(ValueError, match=message):
        agent.on_incident(invalid, NOW)
    assert vars(agent) == before


@pytest.mark.parametrize("connected", [True, False])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("incident_id", UUID(int=7)),
        ("explanation", "Changed body under the same incident identity."),
        ("evidence_event_ids", [UUID(int=8)]),
    ],
)
def test_conflicting_incident_replacement_is_rejected(
    agent: DeterministicSentinelAgent,
    incident: GuardianIncident,
    connected: bool,
    field: str,
    value: object,
) -> None:
    agent.reset(RUN, connected)
    first = agent.on_incident(incident, NOW)
    conflicting = GuardianIncident.model_validate({**incident.model_dump(), field: value})
    before = deepcopy(vars(agent))
    with pytest.raises(ValueError, match="conflicting"):
        agent.on_incident(conflicting, NOW)
    assert vars(agent) == before
    assert agent.on_incident(incident, NOW) == first


def test_caller_mutation_cannot_change_incident_or_pending_decision(
    agent: DeterministicSentinelAgent, incident: GuardianIncident, approval: ATCDecision
) -> None:
    original = incident.model_copy(deep=True)
    pending = agent.on_incident(incident, NOW)
    original_pending = pending.model_copy(deep=True)
    incident.incident_id = UUID(int=99)
    incident.evidence_event_ids.clear()
    pending.evidence_event_ids.clear()
    pending.result = DecisionResult.APPROVED
    assert agent.on_incident(original, NOW) == original_pending
    authorized = agent.decide(approval)
    assert authorized.incident_id == original.incident_id
    assert authorized.evidence_event_ids == original.evidence_event_ids


def test_noncanonical_incident_is_rejected(agent: DeterministicSentinelAgent) -> None:
    before = deepcopy(vars(agent))
    with pytest.raises(ValueError, match="canonical GuardianIncident"):
        agent.on_incident(cast(GuardianIncident, {}), NOW)
    assert vars(agent) == before


def test_invalid_mutated_model_is_revalidated(
    agent: DeterministicSentinelAgent, incident: GuardianIncident
) -> None:
    incident.evidence_event_ids.clear()
    before = deepcopy(vars(agent))
    with pytest.raises(ValueError):
        agent.on_incident(incident, NOW)
    assert vars(agent) == before


def test_invalid_output_time_does_not_partially_accept_incident(
    agent: DeterministicSentinelAgent, incident: GuardianIncident
) -> None:
    before = deepcopy(vars(agent))
    with pytest.raises(ValueError, match="timezone-aware"):
        agent.on_incident(incident, NOW.replace(tzinfo=None))
    assert vars(agent) == before
    assert_pending(agent.on_incident(incident, NOW), incident)


def test_connected_reject_then_approve_and_complete(
    agent: DeterministicSentinelAgent, incident: GuardianIncident, approval: ATCDecision
) -> None:
    pending = agent.on_incident(incident, NOW)
    rejection = approval.model_copy(update={"decision": ATCDecisionType.REJECT, "command_id": UUID(int=9)})
    rejected = agent.decide(rejection)
    assert rejected.result == DecisionResult.REJECTED
    assert rejected.action_type == SimulatorActionType.NO_OP
    assert agent.state == SentinelState.AWAITING_ATC
    assert agent.on_incident(incident, NOW) == pending
    authorized = agent.decide(approval)
    assert authorized.result == DecisionResult.APPROVED
    assert authorized.authorization_source == AuthorizationSource.SIMULATED_ATC
    assert authorized.action_type == approval.requested_action
    assert authorized.sentinel_state == agent.state == SentinelState.SIM_ACTION_RUNNING
    assert SentinelDecision.model_validate_json(authorized.model_dump_json()) == authorized
    agent.complete_action()
    assert agent.state == SentinelState.COMPLETED
    with pytest.raises(ValueError, match="no simulator action"):
        agent.complete_action()


@pytest.mark.parametrize("completed", [False, True])
@pytest.mark.parametrize("replacement", [False, True])
def test_incident_cannot_reopen_action_lifecycle(
    agent: DeterministicSentinelAgent,
    incident: GuardianIncident,
    approval: ATCDecision,
    completed: bool,
    replacement: bool,
) -> None:
    agent.on_incident(incident, NOW)
    authorized = agent.decide(approval)
    if completed:
        agent.complete_action()
    candidate = incident.model_copy(update={"incident_id": UUID(int=10)}) if replacement else incident
    before = deepcopy(vars(agent))
    with pytest.raises(ValueError, match="cannot reopen"):
        agent.on_incident(candidate, NOW)
    with pytest.raises(ValueError, match="not awaiting"):
        agent.decide(approval)
    assert vars(agent) == before
    # Caller-owned authorization cannot mutate retained lifecycle identity either.
    authorized.decision_id = UUID(int=11)
    authorized.evidence_event_ids.clear()
    assert vars(agent) == before


@pytest.mark.parametrize("state", ["initial", "pending", "running", "completed"])
def test_reset_clears_lifecycle_and_isolates_old_run(
    agent: DeterministicSentinelAgent,
    incident: GuardianIncident,
    approval: ATCDecision,
    state: str,
) -> None:
    if state != "initial":
        agent.on_incident(incident, NOW)
    if state in {"running", "completed"}:
        agent.decide(approval)
    if state == "completed":
        agent.complete_action()
    agent.reset(NEW_RUN, False)
    assert agent.state == SentinelState.STANDBY
    before = deepcopy(vars(agent))
    for operation in (
        lambda: agent.on_incident(incident, NOW),
        lambda: agent.decide(approval),
        lambda: agent.set_atc_link(RUN, True),
        agent.complete_action,
    ):
        with pytest.raises(ValueError):
            operation()
        assert vars(agent) == before
    current = incident.model_copy(update={"scenario_run_id": NEW_RUN, "incident_id": UUID(int=12)})
    assert_pending(agent.on_incident(current, NOW), current)
    with pytest.raises(ValueError, match="not awaiting"):
        agent.decide(approval.model_copy(update={"scenario_run_id": NEW_RUN, "incident_id": current.incident_id}))


@pytest.mark.parametrize("field,value", [
    ("scenario_run_id", NEW_RUN),
    ("incident_id", UUID(int=13)),
    ("requested_action", SimulatorActionType.NO_OP),
])
def test_invalid_atc_does_not_mutate(
    agent: DeterministicSentinelAgent,
    incident: GuardianIncident,
    approval: ATCDecision,
    field: str,
    value: object,
) -> None:
    agent.on_incident(incident, NOW)
    before = deepcopy(vars(agent))
    with pytest.raises(ValueError):
        agent.decide(approval.model_copy(update={field: value}))
    assert vars(agent) == before
    assert agent.decide(approval).result == DecisionResult.APPROVED


def test_baseline_link_changes_never_authorize(
    agent: DeterministicSentinelAgent, incident: GuardianIncident, approval: ATCDecision
) -> None:
    first = agent.on_incident(incident, NOW)
    agent.set_atc_link(RUN, True)
    assert agent.on_incident(incident, NOW) == first
    agent.set_atc_link(RUN, False)
    assert agent.state == SentinelState.STANDBY
    assert_pending(agent.on_incident(incident, NOW), incident)
    with pytest.raises(ValueError, match="not awaiting"):
        agent.decide(approval)
    agent.set_atc_link(RUN, True)
    assert agent.state == SentinelState.STANDBY  # Automatic reconnect policy is deferred.
    assert_pending(agent.on_incident(incident, NOW), incident)
    assert agent.state == SentinelState.AWAITING_ATC


@pytest.mark.parametrize("completed", [False, True])
def test_link_changes_do_not_reopen_authorized_lifecycle(
    agent: DeterministicSentinelAgent,
    incident: GuardianIncident,
    approval: ATCDecision,
    completed: bool,
) -> None:
    agent.on_incident(incident, NOW)
    agent.decide(approval)
    if completed:
        agent.complete_action()
    state = agent.state
    agent.set_atc_link(RUN, False)
    agent.set_atc_link(RUN, True)
    assert agent.state == state
    with pytest.raises(ValueError, match="cannot reopen"):
        agent.on_incident(incident, NOW)


def test_completion_without_authorization_is_rejected(
    agent: DeterministicSentinelAgent, incident: GuardianIncident
) -> None:
    for pending in (False, True):
        if pending:
            agent.on_incident(incident, NOW)
        before = deepcopy(vars(agent))
        with pytest.raises(ValueError, match="no simulator action"):
            agent.complete_action()
        assert vars(agent) == before
