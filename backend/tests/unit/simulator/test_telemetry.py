"""SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.contracts.enums import FlightPhase
from app.contracts.models import AircraftTelemetry
from app.modules.simulator import MockAircraftSimulator
from app.scenarios.catalog import SCENARIOS


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
RUN = UUID(int=201)
OTHER_RUN = UUID(int=202)


@pytest.mark.parametrize("scenario_id", tuple(SCENARIOS))
def test_every_scenario_starts_with_canonical_utc_cruise_telemetry(scenario_id: str) -> None:
    simulator = MockAircraftSimulator()
    offset_start = START.astimezone(timezone(timedelta(hours=5, minutes=30)))

    telemetry = simulator.start(RUN, scenario_id, offset_start)

    assert type(telemetry) is AircraftTelemetry
    assert AircraftTelemetry.model_validate_json(telemetry.model_dump_json()) == telemetry
    assert telemetry.simulation_time == START
    assert telemetry.simulation_time.tzinfo == timezone.utc
    assert telemetry.altitude_ft == 35_000.0
    assert telemetry.airspeed_kts == 450.0
    assert telemetry.heading_deg == 90.0
    assert telemetry.flight_phase == FlightPhase.CRUISE
    assert telemetry.active_warning_codes == []


@pytest.mark.parametrize("scenario_id", tuple(SCENARIOS))
def test_equivalent_runs_produce_equivalent_virtual_time_telemetry(scenario_id: str) -> None:
    first = MockAircraftSimulator()
    second = MockAircraftSimulator()
    first.start(RUN, scenario_id, START)
    second.start(OTHER_RUN, scenario_id, START)

    first_results = [first.advance(RUN, START + timedelta(seconds=seconds)) for seconds in (15, 35, 75)]
    second_results = [
        second.advance(OTHER_RUN, START + timedelta(seconds=seconds)) for seconds in (15, 35, 75)
    ]

    assert first_results == second_results
    assert first_results[0].altitude_ft != first_results[1].altitude_ft
    assert first_results[0].airspeed_kts != first_results[1].airspeed_kts


def test_telemetry_is_a_function_of_virtual_time_not_advance_count() -> None:
    incremental = MockAircraftSimulator()
    direct = MockAircraftSimulator()
    incremental.start(RUN, "normal_flight", START)
    direct.start(OTHER_RUN, "normal_flight", START)

    incremental.advance(RUN, START + timedelta(seconds=10))
    incremental.advance(RUN, START + timedelta(seconds=20))
    expected = incremental.advance(RUN, START + timedelta(seconds=30))
    actual = direct.advance(OTHER_RUN, START + timedelta(seconds=30))

    assert actual == expected
    assert direct.advance(OTHER_RUN, START + timedelta(seconds=30)) == actual


@pytest.mark.parametrize("elapsed", (0, 1, 30, 90, 600, 86_400, 31_536_000))
def test_generated_telemetry_remains_inside_contract_bounds(elapsed: int) -> None:
    simulator = MockAircraftSimulator()
    simulator.start(RUN, "dual_pilot_atc_connected", START)

    telemetry = simulator.advance(RUN, START + timedelta(seconds=elapsed))

    assert -1_500 <= telemetry.altitude_ft <= 70_000
    assert 0 <= telemetry.airspeed_kts <= 800
    assert 0 <= telemetry.heading_deg < 360
    assert -90 <= telemetry.latitude <= 90
    assert -180 <= telemetry.longitude <= 180
    assert telemetry.flight_phase == FlightPhase.CRUISE
    assert telemetry.active_warning_codes == []


def test_backward_time_is_rejected_without_changing_telemetry() -> None:
    simulator = MockAircraftSimulator()
    simulator.start(RUN, "normal_flight", START)
    current_time = START + timedelta(seconds=30)
    current = simulator.advance(RUN, current_time)

    with pytest.raises(ValueError, match="cannot move backwards"):
        simulator.advance(RUN, START + timedelta(seconds=29))

    assert simulator.advance(RUN, current_time) == current


def test_stale_run_is_rejected_without_changing_telemetry() -> None:
    simulator = MockAircraftSimulator()
    simulator.start(RUN, "normal_flight", START)
    current_time = START + timedelta(seconds=30)
    current = simulator.advance(RUN, current_time)

    with pytest.raises(ValueError, match="stale scenario_run_id"):
        simulator.advance(OTHER_RUN, current_time + timedelta(seconds=1))

    assert simulator.advance(RUN, current_time) == current


def test_reset_reinitializes_telemetry_and_isolates_the_old_run() -> None:
    simulator = MockAircraftSimulator()
    simulator.start(RUN, "normal_flight", START)
    simulator.advance(RUN, START + timedelta(seconds=30))
    reset_time = START + timedelta(hours=1)

    reset = simulator.reset(OTHER_RUN, "camera_obstructed", reset_time)

    assert reset.simulation_time == reset_time
    assert reset.altitude_ft == 35_000.0
    assert reset.airspeed_kts == 450.0
    with pytest.raises(ValueError, match="stale scenario_run_id"):
        simulator.advance(RUN, reset_time + timedelta(seconds=1))


def test_returned_telemetry_cannot_mutate_internal_state() -> None:
    simulator = MockAircraftSimulator()
    returned = simulator.start(RUN, "normal_flight", START)
    returned.altitude_ft = -1_000
    returned.active_warning_codes.append("CALLER_MUTATION")

    stored = simulator.advance(RUN, START)

    assert stored.altitude_ft == 35_000.0
    assert stored.active_warning_codes == []


def test_invalid_start_inputs_do_not_replace_an_active_run() -> None:
    simulator = MockAircraftSimulator()
    expected = simulator.start(RUN, "normal_flight", START)

    with pytest.raises(ValueError, match="unknown scenario_id"):
        simulator.start(OTHER_RUN, "unknown_scenario", START)
    with pytest.raises(ValueError, match="timezone-aware"):
        simulator.start(OTHER_RUN, "normal_flight", START.replace(tzinfo=None))

    assert simulator.advance(RUN, START) == expected
