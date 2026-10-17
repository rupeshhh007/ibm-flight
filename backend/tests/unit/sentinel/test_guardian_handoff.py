"""SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.

Direct public-module boundary tests, not HTTP/application integration. Recovery
tests characterize the missing revocation signal rather than claim it is fixed.
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid5

import pytest

from app.contracts.enums import (
    ATCDecisionType, AuthorizationSource, DecisionResult, EventSource, EventType,
    GuardianState, IncidentType, PilotId, PilotObservationStatus, SentinelState, SimulatorActionType,
)
from app.contracts.interfaces import GuardianAgent, SentinelAgent
from app.contracts.models import (
    ATCDecision, GuardianIncident, PilotAcknowledgement, PilotObservation, SentinelDecision, StoredEvent,
)
from app.core.clock import VirtualClock
from app.modules.guardian import DeterministicGuardianAgent, GuardianPolicy
from app.modules.sentinel import DeterministicSentinelAgent
from app.modules.simulator import MockAircraftSimulator
from app.modules.vision import MockVisionAdapter
from app.scenarios.catalog import get_scenario
from app.scenarios.runner import ScenarioRunner


RUN_A = UUID(int=701)
RUN_B = UUID(int=702)
BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def forbid_simulator_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("Guardian/Sentinel boundary must not execute simulator operations")

    for method in ("start", "advance", "apply_action", "reset"):
        monkeypatch.setattr(MockAircraftSimulator, method, fail)


def stored_observation(run_id: UUID, seq: int, observation: PilotObservation) -> StoredEvent:
    return StoredEvent(
        seq=seq, event_id=uuid5(run_id, f"observation:{seq}"),
        event_type=EventType.PILOT_OBSERVATION, occurred_at=observation.observed_at,
        source=EventSource.VISION, scenario_run_id=run_id,
        correlation_id=uuid5(run_id, "handoff-test"), payload=observation,
    )


def observation(run_id: UUID, seq: int, pilot: PilotId, at_seconds: int,
                status: PilotObservationStatus = PilotObservationStatus.POSSIBLY_UNRESPONSIVE) -> StoredEvent:
    return stored_observation(run_id, seq, PilotObservation(
        pilot_id=pilot, observed_at=BASE + timedelta(seconds=at_seconds),
        observation_status=status, camera_available=True, face_visible=True,
        eyes_closed=status == PilotObservationStatus.POSSIBLY_UNRESPONSIVE,
        observation_duration_ms=500, observation_quality=0.95,
    ))


def escalate(guardian: GuardianAgent, run_id: UUID) -> tuple[GuardianIncident, list[StoredEvent]]:
    """Same legitimate 2-round pattern as Guardian's own escalation tests.

    Use default policy unchanged; two pilots at t=1 and t=2 satisfy spacing,
    grace, quality and evidence-window requirements without sleeping.
    """
    events = [
        observation(run_id, 1, PilotId.PILOT_1, 1),
        observation(run_id, 2, PilotId.PILOT_2, 1),
        observation(run_id, 3, PilotId.PILOT_1, 2),
        observation(run_id, 4, PilotId.PILOT_2, 2),
    ]
    for event in events[:-1]:
        assert guardian.consume_observation(event) is None
    incident = guardian.consume_observation(events[-1])
    assert type(incident) is GuardianIncident
    assert guardian.state == GuardianState.ESCALATED
    assert guardian.active_incident == incident
    return incident, events


def command(incident: GuardianIncident, number: int, choice: ATCDecisionType = ATCDecisionType.APPROVE,
            issued_at: datetime | None = None) -> ATCDecision:
    return ATCDecision(
        command_id=UUID(int=number), scenario_run_id=incident.scenario_run_id,
        incident_id=incident.incident_id, decision=choice,
        requested_action=SimulatorActionType.SIM_STABILIZE, operator_id="fictional-atc",
        issued_at=issued_at if issued_at is not None else incident.created_at,
    )


def assert_pending(decision: SentinelDecision, incident: GuardianIncident, state: SentinelState) -> None:
    assert type(decision) is SentinelDecision
    assert SentinelDecision.model_validate_json(decision.model_dump_json()) == decision
    assert decision.incident_id == incident.incident_id
    assert decision.scenario_run_id == incident.scenario_run_id
    assert decision.evidence_event_ids == incident.evidence_event_ids
    assert decision.sentinel_state == state
    assert decision.result == DecisionResult.PENDING
    assert decision.action_type == SimulatorActionType.NO_OP
    assert decision.authorization_source == AuthorizationSource.NONE


def test_real_guardian_incident_is_accepted_with_current_run_evidence() -> None:
    guardian = DeterministicGuardianAgent()
    sentinel = DeterministicSentinelAgent()
    assert isinstance(guardian, GuardianAgent)
    assert isinstance(sentinel, SentinelAgent)
    assert guardian.policy == GuardianPolicy()
    guardian.reset(RUN_A)
    sentinel.reset(RUN_A, True)
    incident, events = escalate(guardian, RUN_A)
    assert incident.incident_type == IncidentType.DUAL_PILOT_UNRESPONSIVE
    assert incident.created_at == events[-1].occurred_at == events[-1].payload.observed_at
    assert incident.evidence_event_ids == [event.event_id for event in events]
    assert all(event.scenario_run_id == incident.scenario_run_id == RUN_A for event in events)
    assert GuardianIncident.model_validate_json(incident.model_dump_json()) == incident
    pending = sentinel.on_incident(incident, events[-1].occurred_at)
    assert_pending(pending, incident, SentinelState.AWAITING_ATC)
    assert sentinel.state == SentinelState.AWAITING_ATC
    # Guardian emits once; orchestration must not treat None as incident revocation.
    assert guardian.consume_observation(events[-1]) is None
    assert guardian.active_incident == incident
    assert sentinel.on_incident(incident, events[-1].occurred_at) == pending


def test_connected_real_incident_reject_then_approve_preserves_replay_guards() -> None:
    guardian, sentinel = DeterministicGuardianAgent(), DeterministicSentinelAgent()
    guardian.reset(RUN_A)
    sentinel.reset(RUN_A, True)
    incident, events = escalate(guardian, RUN_A)
    sentinel.on_incident(incident, events[-1].occurred_at)
    rejection = command(incident, 710, ATCDecisionType.REJECT)
    rejected = sentinel.decide(rejection)
    assert rejected.result == DecisionResult.REJECTED
    assert rejected.action_type == SimulatorActionType.NO_OP
    assert sentinel.state == SentinelState.AWAITING_ATC
    approval = command(incident, 711)
    authorized = sentinel.decide(approval)
    assert authorized.result == DecisionResult.APPROVED
    assert authorized.authorization_source == AuthorizationSource.SIMULATED_ATC
    assert authorized.action_type == approval.requested_action
    assert authorized.scenario_run_id == incident.scenario_run_id
    assert authorized.incident_id == incident.incident_id
    assert authorized.evidence_event_ids == incident.evidence_event_ids
    assert sentinel.state == SentinelState.SIM_ACTION_RUNNING
    for consumed in (rejection, approval):
        before = deepcopy(vars(sentinel))
        with pytest.raises(ValueError, match="replayed command_id"):
            sentinel.decide(consumed)
        assert vars(sentinel) == before
    before = deepcopy(vars(sentinel))
    with pytest.raises(ValueError, match="not awaiting"):
        sentinel.decide(command(incident, 712))
    assert vars(sentinel) == before


def test_offline_real_incident_requires_explicit_redelivery_after_reconnect() -> None:
    guardian, sentinel = DeterministicGuardianAgent(), DeterministicSentinelAgent()
    guardian.reset(RUN_A)
    sentinel.reset(RUN_A, False)
    incident, events = escalate(guardian, RUN_A)
    assert_pending(sentinel.on_incident(incident, events[-1].occurred_at), incident, SentinelState.STANDBY)
    assert sentinel.state == SentinelState.STANDBY
    sentinel.set_atc_link(RUN_A, True)
    assert sentinel.state == SentinelState.STANDBY
    approval = command(incident, 713, issued_at=incident.created_at + timedelta(seconds=1))
    before = deepcopy(vars(sentinel))
    with pytest.raises(ValueError, match="not awaiting"):
        sentinel.decide(approval)
    assert vars(sentinel) == before
    assert_pending(sentinel.on_incident(incident, approval.issued_at), incident, SentinelState.AWAITING_ATC)
    assert sentinel.decide(approval).result == DecisionResult.APPROVED


@pytest.mark.parametrize("stage", ["waiting", "running", "completed"])
def test_both_agents_reset_to_new_run_and_exclude_old_incident_evidence(stage: str) -> None:
    guardian, sentinel = DeterministicGuardianAgent(), DeterministicSentinelAgent()
    guardian.reset(RUN_A)
    sentinel.reset(RUN_A, True)
    old_incident, old_events = escalate(guardian, RUN_A)
    sentinel.on_incident(old_incident, old_incident.created_at)
    rejection, approval = command(old_incident, 714, ATCDecisionType.REJECT), command(old_incident, 715)
    sentinel.decide(rejection)
    if stage in {"running", "completed"}:
        sentinel.decide(approval)
    if stage == "completed":
        sentinel.complete_action()
    guardian.reset(RUN_B)
    sentinel.reset(RUN_B, True)
    assert guardian.state == GuardianState.NORMAL
    assert guardian.active_incident is None
    for operation in (
        lambda: sentinel.on_incident(old_incident, old_incident.created_at),
        lambda: sentinel.decide(approval), lambda: sentinel.decide(rejection),
        lambda: sentinel.set_atc_link(RUN_A, False),
    ):
        before = deepcopy(vars(sentinel))
        with pytest.raises(ValueError, match="scenario_run_id"):
            operation()
        assert vars(sentinel) == before
    for event in old_events:
        before = (guardian.state, guardian.active_incident)
        with pytest.raises(ValueError, match="scenario_run_id"):
            guardian.consume_observation(event)
        assert (guardian.state, guardian.active_incident) == before
    current, current_events = escalate(guardian, RUN_B)
    assert current.incident_id != old_incident.incident_id
    assert set(current.evidence_event_ids).isdisjoint(old_incident.evidence_event_ids)
    assert_pending(sentinel.on_incident(current, current_events[-1].occurred_at), current, SentinelState.AWAITING_ATC)
    assert sentinel.decide(command(current, 716)).result == DecisionResult.APPROVED


@pytest.mark.parametrize("recovery", ["acknowledgement", "observations"])
def test_characterize_guardian_recovery_without_a_sentinel_revocation_signal(recovery: str) -> None:
    """Known integration gap: retained local eligibility is not auto-revoked.

    API acknowledgement clears its snapshot incident, blocking API approval.
    Observation-driven recovery is not refreshed into that snapshot today.
    This test is not a claim that stale eligibility should remain in Phase 5B.
    """
    guardian, sentinel = DeterministicGuardianAgent(), DeterministicSentinelAgent()
    guardian.reset(RUN_A)
    sentinel.reset(RUN_A, True)
    incident, _ = escalate(guardian, RUN_A)
    pending = sentinel.on_incident(incident, incident.created_at)
    before = deepcopy(vars(sentinel))
    if recovery == "acknowledgement":
        guardian.acknowledge(PilotAcknowledgement(
            command_id=UUID(int=717), scenario_run_id=RUN_A, pilot_id=PilotId.PILOT_1,
            alert_id=incident.incident_id, acknowledged_at=incident.created_at,
        ))
    else:
        seq = 5
        for seconds in (3, 4):
            for pilot in PilotId:
                assert guardian.consume_observation(observation(
                    RUN_A, seq, pilot, seconds, PilotObservationStatus.RESPONSIVE,
                )) is None
                seq += 1
    assert guardian.state == GuardianState.RECOVERING
    assert guardian.active_incident is None
    assert vars(sentinel) == before
    assert sentinel.on_incident(incident, incident.created_at) == pending
    # Demonstrates what remains possible through direct Sentinel calls, not HTTP.
    assert sentinel.decide(command(incident, 718)).result == DecisionResult.APPROVED


@pytest.mark.parametrize("deltas, expected_incident", [((1000, 1000), True), ((2000,), False)])
def test_current_scenario_batch_timestamps_against_real_guardian_policy(
    deltas: tuple[int, ...], expected_incident: bool,
) -> None:
    """Mirror public runner/vision/clock timing, without wiring an application.

    A single large advance stamps both scheduled rounds at t=2, losing the
    independent spacing/grace. Two advances preserve t=1/t=2 and can escalate.
    """
    guardian, sentinel = DeterministicGuardianAgent(), DeterministicSentinelAgent()
    guardian.reset(RUN_A)
    sentinel.reset(RUN_A, True)
    clock = VirtualClock(BASE)
    runner = ScenarioRunner(get_scenario("dual_pilot_atc_connected"))
    vision = MockVisionAdapter()
    vision.configure_scenario("dual_pilot_atc_connected")
    seq = 0
    incident = None
    for delta in deltas:
        now = clock.advance(delta)
        for pilot in runner.advance(delta):
            seq += 1
            event = stored_observation(RUN_A, seq, vision.observe(pilot, now))
            emitted = guardian.consume_observation(event)
            if emitted is not None:
                assert incident is None
                incident = emitted
                assert incident.created_at == event.occurred_at == now
                assert_pending(sentinel.on_incident(incident, now), incident, SentinelState.AWAITING_ATC)
    assert (incident is not None) == expected_incident
    if incident is not None:
        assert sentinel.decide(command(incident, 719, issued_at=clock.now())).result == DecisionResult.APPROVED
    else:
        assert guardian.active_incident is None
        assert sentinel.state == SentinelState.STANDBY


def test_invalid_boundary_input_and_clock_order_do_not_mutate_sentinel() -> None:
    guardian, sentinel = DeterministicGuardianAgent(), DeterministicSentinelAgent()
    guardian.reset(RUN_A)
    sentinel.reset(RUN_A, True)
    incident, _ = escalate(guardian, RUN_A)
    for invalid in (
        incident.model_copy(update={"scenario_run_id": RUN_B}),
        incident.model_copy(update={"guardian_state": GuardianState.RECOVERING}),
    ):
        before = deepcopy(vars(sentinel))
        with pytest.raises(ValueError, match="scenario_run_id|ESCALATED"):
            sentinel.on_incident(invalid, incident.created_at)
        assert vars(sentinel) == before
    before = deepcopy(vars(sentinel))
    with pytest.raises(ValueError, match="observation cannot precede"):
        sentinel.on_incident(incident, incident.created_at - timedelta(microseconds=1))
    assert vars(sentinel) == before
    observed_at = incident.created_at + timedelta(seconds=1)
    sentinel.on_incident(incident, observed_at)
    approval = command(incident, 720)
    before = deepcopy(vars(sentinel))
    with pytest.raises(ValueError, match="first accepted incident observation"):
        sentinel.decide(approval)
    assert vars(sentinel) == before
    assert sentinel.decide(approval.model_copy(update={"issued_at": observed_at})).result == DecisionResult.APPROVED
