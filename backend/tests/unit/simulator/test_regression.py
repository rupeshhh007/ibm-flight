"""SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE."""

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Callable, cast
from uuid import UUID

import pytest

from app.contracts.enums import (
    AuthorizationSource,
    DecisionResult,
    FlightPhase,
    SentinelState,
    SimulatorActionType,
)
from app.contracts.models import AircraftTelemetry, SentinelDecision
from app.modules.simulator import MockAircraftSimulator
from app.scenarios.catalog import SCENARIOS


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
RUN = UUID(int=501)
OTHER_RUN = UUID(int=502)
INCIDENT = UUID(int=503)
DECISION = UUID(int=504)


def _authorization(
    *,
    run_id: UUID = RUN,
    action: SimulatorActionType = SimulatorActionType.SIM_STABILIZE,
    source: AuthorizationSource = AuthorizationSource.SIMULATED_ATC,
    result: DecisionResult = DecisionResult.APPROVED,
    state: SentinelState = SentinelState.SIM_ACTION_RUNNING,
    executed_at: datetime = START + timedelta(seconds=20),
    decision_id: UUID = DECISION,
) -> SentinelDecision:
    return SentinelDecision(
        decision_id=decision_id,
        scenario_run_id=run_id,
        incident_id=INCIDENT,
        sentinel_state=state,
        action_type=action,
        authorization_source=source,
        reason="Deterministic Phase 5 authorization fixture.",
        evidence_event_ids=[],
        executed_at=executed_at,
        result=result,
    )


def _state(simulator: MockAircraftSimulator) -> tuple[object, ...]:
    return (
        simulator._run_id,
        simulator._scenario_id,
        simulator._started_at,
        simulator._telemetry.model_copy(deep=True) if simulator._telemetry else None,
        simulator._last_action.model_copy(deep=True) if simulator._last_action else None,
        tuple(item.model_copy(deep=True) for item in simulator._action_history),
        frozenset(simulator._executed_authorization_ids),
    )


def _telemetry_values() -> dict[str, object]:
    return {
        "aircraft_id": "AEROGUARD-SIM-BOUNDARY",
        "simulation_time": START,
        "altitude_ft": 35_000.0,
        "airspeed_kts": 450.0,
        "heading_deg": 90.0,
        "latitude": 19.0760,
        "longitude": 72.8777,
        "flight_phase": FlightPhase.CRUISE,
        "active_warning_codes": [],
    }


@pytest.mark.parametrize(
    ("field", "lower", "upper"),
    (
        ("altitude_ft", -1_500.0, 70_000.0),
        ("airspeed_kts", 0.0, 800.0),
        ("heading_deg", 0.0, 359.999999),
        ("latitude", -90.0, 90.0),
        ("longitude", -180.0, 180.0),
    ),
)
def test_telemetry_contract_numeric_boundaries_are_accepted(
    field: str,
    lower: float,
    upper: float,
) -> None:
    lower_values = _telemetry_values()
    upper_values = _telemetry_values()
    lower_values[field] = lower
    upper_values[field] = upper

    assert getattr(AircraftTelemetry.model_validate(lower_values), field) == lower
    assert getattr(AircraftTelemetry.model_validate(upper_values), field) == upper


@pytest.mark.parametrize(
    ("field", "value"),
    tuple(
        (field, value)
        for field in ("altitude_ft", "airspeed_kts", "heading_deg", "latitude", "longitude")
        for value in (float("nan"), float("inf"), float("-inf"))
    ),
)
def test_telemetry_contract_rejects_nonfinite_numeric_values(field: str, value: float) -> None:
    values = _telemetry_values()
    values[field] = value

    with pytest.raises(ValueError):
        AircraftTelemetry.model_validate(values)


@pytest.mark.parametrize("scenario_id", tuple(SCENARIOS))
@pytest.mark.parametrize(
    "elapsed",
    (0, 1, 90, 600_000, 31_536_000, 315_360_000),
)
def test_all_numeric_telemetry_remains_finite_for_large_virtual_times(
    scenario_id: str,
    elapsed: int,
) -> None:
    simulator = MockAircraftSimulator()
    simulator.start(RUN, scenario_id, START)

    telemetry = simulator.advance(RUN, START + timedelta(seconds=elapsed))

    numeric_values = (
        telemetry.altitude_ft,
        telemetry.airspeed_kts,
        telemetry.heading_deg,
        telemetry.latitude,
        telemetry.longitude,
    )
    assert all(isfinite(value) for value in numeric_values)
    assert AircraftTelemetry.model_validate(telemetry.model_dump()) == telemetry


def test_invalid_run_identifier_does_not_replace_active_telemetry() -> None:
    simulator = MockAircraftSimulator()
    expected = simulator.start(RUN, "normal_flight", START)

    with pytest.raises(ValueError, match="scenario_run_id must be a UUID"):
        simulator.start(cast(UUID, "not-a-uuid"), "camera_obstructed", START + timedelta(hours=1))

    assert simulator.advance(RUN, START) == expected


InvalidAttempt = Callable[[MockAircraftSimulator], None]


def _mismatched_run(simulator: MockAircraftSimulator) -> None:
    simulator.apply_action(
        RUN,
        SimulatorActionType.SIM_STABILIZE,
        _authorization(run_id=OTHER_RUN),
        START + timedelta(seconds=20),
    )


def _mismatched_action(simulator: MockAircraftSimulator) -> None:
    simulator.apply_action(
        RUN,
        SimulatorActionType.SIM_ABORT,
        _authorization(),
        START + timedelta(seconds=20),
    )


def _missing_source(simulator: MockAircraftSimulator) -> None:
    simulator.apply_action(
        RUN,
        SimulatorActionType.SIM_STABILIZE,
        _authorization(source=AuthorizationSource.NONE),
        START + timedelta(seconds=20),
    )


def _nonapproved_result(simulator: MockAircraftSimulator) -> None:
    simulator.apply_action(
        RUN,
        SimulatorActionType.SIM_STABILIZE,
        _authorization(result=DecisionResult.REJECTED),
        START + timedelta(seconds=20),
    )


def _invalid_sentinel_state(simulator: MockAircraftSimulator) -> None:
    simulator.apply_action(
        RUN,
        SimulatorActionType.SIM_STABILIZE,
        _authorization(state=SentinelState.COMPLETED),
        START + timedelta(seconds=20),
    )


def _stale_decision_time(simulator: MockAircraftSimulator) -> None:
    simulator.apply_action(
        RUN,
        SimulatorActionType.SIM_STABILIZE,
        _authorization(executed_at=START - timedelta(microseconds=1)),
        START + timedelta(seconds=20),
    )


def _backdated_application(simulator: MockAircraftSimulator) -> None:
    simulator.apply_action(
        RUN,
        SimulatorActionType.SIM_STABILIZE,
        _authorization(executed_at=START + timedelta(seconds=10)),
        START + timedelta(seconds=15),
    )


@pytest.mark.parametrize(
    "attempt",
    (
        _mismatched_run,
        _mismatched_action,
        _missing_source,
        _nonapproved_result,
        _invalid_sentinel_state,
        _stale_decision_time,
        _backdated_application,
    ),
    ids=(
        "authorization-run",
        "authorization-action",
        "authorization-source",
        "decision-result",
        "sentinel-state",
        "decision-time",
        "application-time",
    ),
)
def test_combined_authorization_rejections_preserve_complete_state_and_do_not_consume_decision(
    attempt: InvalidAttempt,
) -> None:
    simulator = MockAircraftSimulator()
    simulator.start(RUN, "dual_pilot_atc_connected", START)
    simulator.advance(RUN, START + timedelta(seconds=20))
    before = _state(simulator)

    with pytest.raises(ValueError):
        attempt(simulator)

    assert _state(simulator) == before
    accepted = simulator.apply_action(
        RUN,
        SimulatorActionType.SIM_STABILIZE,
        _authorization(),
        START + timedelta(seconds=20),
    )
    assert accepted.result == DecisionResult.EXECUTED


def test_corrupted_canonical_authorization_is_rejected_atomically() -> None:
    simulator = MockAircraftSimulator()
    simulator.start(RUN, "dual_pilot_atc_connected", START)
    decision = _authorization()
    decision.reason = ""
    before = _state(simulator)

    with pytest.raises(ValueError, match="well-formed canonical SentinelDecision"):
        simulator.apply_action(
            RUN,
            SimulatorActionType.SIM_STABILIZE,
            decision,
            START + timedelta(seconds=20),
        )

    assert _state(simulator) == before


def test_reset_rejects_old_authorization_then_accepts_fresh_new_run_authorization() -> None:
    simulator = MockAircraftSimulator()
    simulator.start(RUN, "dual_pilot_atc_connected", START)
    old_authorization = _authorization()
    reset_at = START + timedelta(hours=1)
    simulator.reset(OTHER_RUN, "dual_pilot_atc_connected", reset_at)

    before = _state(simulator)
    with pytest.raises(ValueError, match="does not belong"):
        simulator.apply_action(
            OTHER_RUN,
            SimulatorActionType.SIM_STABILIZE,
            old_authorization,
            reset_at,
        )
    assert _state(simulator) == before

    fresh = _authorization(
        run_id=OTHER_RUN,
        executed_at=reset_at,
        decision_id=UUID(int=505),
    )
    result = simulator.apply_action(
        OTHER_RUN,
        SimulatorActionType.SIM_STABILIZE,
        fresh,
        reset_at,
    )
    assert result.result == DecisionResult.EXECUTED
    assert simulator._executed_authorization_ids == {UUID(int=505)}
