"""SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE."""

from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID

import pytest

from app.contracts.enums import (
    AuthorizationSource,
    DecisionResult,
    SentinelState,
    SimulatorActionType,
)
from app.contracts.models import SentinelDecision, SimulatorActionPayload
from app.modules.simulator import MockAircraftSimulator


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
RUN = UUID(int=401)
OTHER_RUN = UUID(int=402)
INCIDENT = UUID(int=403)
EVIDENCE = UUID(int=404)


def authorization(
    *,
    run_id: UUID = RUN,
    action: SimulatorActionType = SimulatorActionType.SIM_STABILIZE,
    source: AuthorizationSource = AuthorizationSource.SIMULATED_ATC,
    result: DecisionResult = DecisionResult.APPROVED,
    state: SentinelState = SentinelState.SIM_ACTION_RUNNING,
    executed_at: datetime = START + timedelta(seconds=10),
    decision_id: UUID = UUID(int=405),
) -> SentinelDecision:
    return SentinelDecision(
        decision_id=decision_id,
        scenario_run_id=run_id,
        incident_id=INCIDENT,
        sentinel_state=state,
        action_type=action,
        authorization_source=source,
        reason="Canonical deterministic test authorization.",
        evidence_event_ids=[EVIDENCE],
        executed_at=executed_at,
        result=result,
    )


def started() -> MockAircraftSimulator:
    simulator = MockAircraftSimulator()
    simulator.start(RUN, "dual_pilot_atc_connected", START)
    return simulator


def apply(
    simulator: MockAircraftSimulator,
    decision: SentinelDecision,
    *,
    run_id: UUID = RUN,
    action: SimulatorActionType = SimulatorActionType.SIM_STABILIZE,
    applied_at: datetime = START + timedelta(seconds=10),
) -> SimulatorActionPayload:
    return simulator.apply_action(run_id, action, decision, applied_at)


@pytest.mark.parametrize("action", tuple(SimulatorActionType))
@pytest.mark.parametrize(
    "source",
    (AuthorizationSource.SIMULATED_ATC, AuthorizationSource.LOCAL_FALLBACK),
)
def test_every_canonical_action_has_a_safe_symbolic_result(
    action: SimulatorActionType,
    source: AuthorizationSource,
) -> None:
    simulator = started()
    before = simulator.advance(RUN, START + timedelta(seconds=10))

    result = apply(simulator, authorization(action=action, source=source), action=action)

    assert type(result) is SimulatorActionPayload
    assert SimulatorActionPayload.model_validate_json(result.model_dump_json()) == result
    assert result.scenario_run_id == RUN
    assert result.action_type == action
    assert result.authorization_source == source
    assert result.authorized is True
    assert result.result == DecisionResult.EXECUTED
    assert result.applied_at == START + timedelta(seconds=10)
    assert simulator.advance(RUN, START + timedelta(seconds=10)) == before
    assert simulator._last_action == result
    assert simulator._action_history == [result]
    assert simulator._executed_authorization_ids == {UUID(int=405)}


@pytest.mark.parametrize(
    "invalid_action",
    (
        "SIM_STABILIZE",
        "UNKNOWN",
        "land the aircraft",
        "turn left",
        "emergency landing",
        1,
        None,
        object(),
    ),
)
def test_noncanonical_action_inputs_are_rejected_atomically(invalid_action: object) -> None:
    simulator = started()

    with pytest.raises(ValueError, match="canonical SimulatorActionType"):
        apply(
            simulator,
            authorization(),
            action=cast(SimulatorActionType, invalid_action),
        )

    assert simulator._last_action is None
    assert simulator._action_history == []
    assert simulator._executed_authorization_ids == set()
    assert apply(simulator, authorization()).result == DecisionResult.EXECUTED


def test_action_requires_the_active_run_before_reading_authorization() -> None:
    simulator = started()

    with pytest.raises(ValueError, match="stale scenario_run_id"):
        apply(simulator, cast(SentinelDecision, None), run_id=OTHER_RUN)

    assert simulator._action_history == []


@pytest.mark.parametrize("authorized_run", (OTHER_RUN, UUID(int=499)))
def test_authorization_must_belong_to_the_active_run(authorized_run: UUID) -> None:
    simulator = started()

    with pytest.raises(ValueError, match="does not belong"):
        apply(simulator, authorization(run_id=authorized_run))

    assert simulator._action_history == []


@pytest.mark.parametrize("authorized_action", tuple(SimulatorActionType))
def test_authorization_cannot_be_substituted_for_another_action(
    authorized_action: SimulatorActionType,
) -> None:
    requested = (
        SimulatorActionType.SIM_ABORT
        if authorized_action != SimulatorActionType.SIM_ABORT
        else SimulatorActionType.SIM_STABILIZE
    )
    simulator = started()

    with pytest.raises(ValueError, match="does not match"):
        apply(simulator, authorization(action=authorized_action), action=requested)

    assert simulator._action_history == []


def test_none_authorization_source_is_rejected() -> None:
    simulator = started()

    with pytest.raises(ValueError, match="source NONE"):
        apply(simulator, authorization(source=AuthorizationSource.NONE))

    assert simulator._action_history == []


@pytest.mark.parametrize("result", tuple(item for item in DecisionResult if item != DecisionResult.APPROVED))
def test_every_nonapproved_decision_result_is_rejected(result: DecisionResult) -> None:
    simulator = started()

    with pytest.raises(ValueError, match="APPROVED"):
        apply(simulator, authorization(result=result))

    assert simulator._action_history == []


@pytest.mark.parametrize(
    "state",
    tuple(item for item in SentinelState if item != SentinelState.SIM_ACTION_RUNNING),
)
def test_every_nonrunning_sentinel_state_is_rejected(state: SentinelState) -> None:
    simulator = started()

    with pytest.raises(ValueError, match="SIM_ACTION_RUNNING"):
        apply(simulator, authorization(state=state))

    assert simulator._action_history == []


@pytest.mark.parametrize("invalid_authorization", (None, {}, "APPROVED", object()))
def test_malformed_authorization_is_rejected(invalid_authorization: object) -> None:
    simulator = started()

    with pytest.raises(ValueError, match="canonical SentinelDecision"):
        apply(simulator, cast(SentinelDecision, invalid_authorization))

    assert simulator._action_history == []


def test_mutated_authorization_is_revalidated_and_rejected() -> None:
    simulator = started()
    decision = authorization()
    decision.result = cast(DecisionResult, "APPROVED")

    with pytest.raises(ValueError, match="well-formed canonical SentinelDecision"):
        apply(simulator, decision)

    assert simulator._action_history == []


def test_incomplete_constructed_authorization_is_rejected_without_attribute_error() -> None:
    simulator = started()
    incomplete = SentinelDecision.model_construct(decision_id=UUID(int=405))

    with pytest.raises(ValueError, match="well-formed canonical SentinelDecision"):
        apply(simulator, incomplete)

    assert simulator._action_history == []


def test_authorization_cannot_predate_the_active_run() -> None:
    simulator = started()

    with pytest.raises(ValueError, match="predates"):
        apply(simulator, authorization(executed_at=START - timedelta(microseconds=1)))

    assert simulator._action_history == []


def test_wall_clock_authorization_is_not_compared_to_virtual_application_time() -> None:
    simulator = started()
    wall_clock_time = START + timedelta(days=30)

    result = apply(
        simulator,
        authorization(executed_at=wall_clock_time),
        applied_at=START + timedelta(seconds=10),
    )

    assert result.result == DecisionResult.EXECUTED


def test_action_application_cannot_precede_current_virtual_time() -> None:
    simulator = started()
    simulator.advance(RUN, START + timedelta(seconds=20))

    with pytest.raises(ValueError, match="current simulation time"):
        apply(
            simulator,
            authorization(executed_at=START + timedelta(seconds=10)),
            applied_at=START + timedelta(seconds=15),
        )

    assert simulator._action_history == []


def test_naive_application_time_is_rejected_without_mutation() -> None:
    simulator = started()

    with pytest.raises(ValueError, match="applied_at must be a timezone-aware datetime"):
        apply(simulator, authorization(), applied_at=START.replace(tzinfo=None))

    assert simulator._action_history == []


def test_replayed_authorization_cannot_repeat_side_effects() -> None:
    simulator = started()
    decision = authorization()
    first = apply(simulator, decision)

    with pytest.raises(ValueError, match="already executed"):
        apply(simulator, decision)

    assert simulator._last_action == first
    assert simulator._action_history == [first]
    assert simulator._executed_authorization_ids == {decision.decision_id}


def test_separate_authorization_cannot_reopen_terminal_run_state() -> None:
    simulator = started()
    first = apply(simulator, authorization())
    separate = authorization(decision_id=UUID(int=406))

    with pytest.raises(ValueError, match="terminal action state"):
        apply(simulator, separate)

    assert simulator._last_action == first
    assert simulator._action_history == [first]
    assert simulator._executed_authorization_ids == {UUID(int=405)}


def test_returned_action_payload_cannot_mutate_internal_history() -> None:
    simulator = started()
    returned = apply(simulator, authorization())
    returned.reason = "CALLER MUTATION"

    assert simulator._last_action is not None
    assert simulator._last_action.reason != returned.reason
    assert simulator._action_history[0].reason != returned.reason


def test_reset_clears_action_state_and_blocks_old_run_and_authorization() -> None:
    simulator = started()
    apply(simulator, authorization())
    reset_at = START + timedelta(hours=1)

    reset = simulator.reset(OTHER_RUN, "camera_obstructed", reset_at)

    assert reset.simulation_time == reset_at
    assert simulator._last_action is None
    assert simulator._action_history == []
    assert simulator._executed_authorization_ids == set()
    with pytest.raises(ValueError, match="stale scenario_run_id"):
        apply(simulator, authorization(), run_id=RUN, applied_at=reset_at)
    with pytest.raises(ValueError, match="does not belong"):
        apply(
            simulator,
            authorization(),
            run_id=OTHER_RUN,
            applied_at=reset_at,
        )


def test_invalid_reset_is_atomic_for_action_history() -> None:
    simulator = started()
    first = apply(simulator, authorization())

    with pytest.raises(ValueError, match="unknown scenario_id"):
        simulator.reset(OTHER_RUN, "unknown_scenario", START + timedelta(hours=1))
    with pytest.raises(ValueError, match="timezone-aware"):
        simulator.reset(OTHER_RUN, "normal_flight", START.replace(tzinfo=None))

    assert simulator._run_id == RUN
    assert simulator._last_action == first
    assert simulator._action_history == [first]
    assert simulator._executed_authorization_ids == {UUID(int=405)}


def test_equivalent_resets_restore_equivalent_functional_outcomes() -> None:
    first = started()
    second = started()
    apply(first, authorization())
    apply(second, authorization())
    reset_at = START + timedelta(hours=1)

    first_telemetry = first.reset(OTHER_RUN, "normal_flight", reset_at)
    second_telemetry = second.reset(OTHER_RUN, "normal_flight", reset_at)

    assert first_telemetry == second_telemetry
    assert first._last_action == second._last_action is None
    assert first._action_history == second._action_history == []
    assert first._executed_authorization_ids == second._executed_authorization_ids == set()
