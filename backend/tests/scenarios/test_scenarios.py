"""SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE."""

from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID

import pytest

from app.contracts.enums import PilotId, PilotObservationStatus
from app.contracts.models import AircraftTelemetry, ScenarioMetadata
from app.modules.simulator import MockAircraftSimulator
from app.modules.vision import MockVisionAdapter
from app.scenarios.catalog import SCENARIOS, ScenarioDefinition, get_scenario, list_scenarios
from app.scenarios.runner import ScenarioRunner


SCENARIO_IDS = (
    "normal_flight",
    "single_pilot_unresponsive",
    "dual_pilot_atc_connected",
    "dual_pilot_atc_disconnected",
    "camera_obstructed",
)
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _definition(schedule: tuple[tuple[int, PilotId], ...]) -> ScenarioDefinition:
    return ScenarioDefinition(
        metadata=ScenarioMetadata(
            scenario_id="normal_flight",
            name="Synthetic scheduling fixture",
            description="Deterministic runner-only fixture.",
            p0_behavior="No authorization or operational aviation behavior.",
        ),
        atc_connected=True,
        observation_schedule=schedule,
    )


def _observations(scenario_id: str, deltas: tuple[int, ...] = (1_000, 1_000)) -> list[tuple]:
    runner = ScenarioRunner(get_scenario(scenario_id))
    vision = MockVisionAdapter()
    vision.configure_scenario(scenario_id)
    elapsed_ms = 0
    observed = []
    for delta_ms in deltas:
        elapsed_ms += delta_ms
        observed_at = START + timedelta(milliseconds=elapsed_ms)
        for pilot_id in runner.advance(delta_ms):
            observation = vision.observe(pilot_id, observed_at)
            observed.append(
                (
                    elapsed_ms,
                    observation.pilot_id,
                    observation.observation_status,
                    observation.camera_available,
                    observation.face_visible,
                )
            )
    return observed


def test_catalog_contains_exactly_the_five_frozen_scenarios() -> None:
    assert tuple(SCENARIOS) == SCENARIO_IDS
    assert tuple(item.scenario_id for item in list_scenarios()) == SCENARIO_IDS
    assert len(set(SCENARIOS)) == len(SCENARIO_IDS)
    for scenario_id in SCENARIO_IDS:
        definition = get_scenario(scenario_id)
        assert definition.metadata.scenario_id == scenario_id
        assert definition.observation_schedule == (
            (1_000, PilotId.PILOT_1),
            (1_000, PilotId.PILOT_2),
            (2_000, PilotId.PILOT_1),
            (2_000, PilotId.PILOT_2),
        )


def test_catalog_lookup_is_deterministic_and_returns_defensive_metadata() -> None:
    first = get_scenario("normal_flight")
    second = get_scenario("normal_flight")
    assert first == second
    assert first is not second
    assert first.metadata is not second.metadata

    first.metadata.name = "CALLER MUTATION"
    listed = list_scenarios()
    listed[0].description = "CALLER MUTATION"

    current = get_scenario("normal_flight")
    assert current.metadata.name == "Normal flight"
    assert current.metadata.description == "Both synthetic pilots remain responsive."


def test_unknown_scenario_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown scenario_id"):
        get_scenario("unsupported_scenario")


def test_inclusive_boundaries_and_exactly_once_processing() -> None:
    runner = ScenarioRunner(get_scenario("normal_flight"))

    assert runner.advance(999) == []
    assert runner.advance(1) == [PilotId.PILOT_1, PilotId.PILOT_2]
    assert runner.advance(999) == []
    assert runner.advance(1) == [PilotId.PILOT_1, PilotId.PILOT_2]
    assert runner.advance(1) == []
    assert runner.elapsed_ms == 2_001


def test_large_advance_crosses_all_events_in_chronological_stable_order() -> None:
    definition = _definition(
        (
            (2_000, PilotId.PILOT_2),
            (1_000, PilotId.PILOT_2),
            (1_000, PilotId.PILOT_1),
            (3_000, PilotId.PILOT_1),
        )
    )
    runner = ScenarioRunner(definition)

    assert runner.advance(3_500) == [
        PilotId.PILOT_2,
        PilotId.PILOT_1,
        PilotId.PILOT_2,
        PilotId.PILOT_1,
    ]
    assert runner.advance(1) == []


def test_direct_and_incremental_advancement_produce_equivalent_events() -> None:
    direct = ScenarioRunner(get_scenario("dual_pilot_atc_connected"))
    incremental = ScenarioRunner(get_scenario("dual_pilot_atc_connected"))

    direct_events = direct.advance(2_500)
    incremental_events = (
        incremental.advance(500)
        + incremental.advance(500)
        + incremental.advance(999)
        + incremental.advance(1)
        + incremental.advance(500)
    )

    assert direct_events == incremental_events == [
        PilotId.PILOT_1,
        PilotId.PILOT_2,
        PilotId.PILOT_1,
        PilotId.PILOT_2,
    ]


@pytest.mark.parametrize("delta_ms", (0, -1, 600_001, 1.5, True, "1000", None))
def test_invalid_advance_is_atomic_and_later_valid_advance_succeeds(delta_ms: object) -> None:
    runner = ScenarioRunner(get_scenario("normal_flight"))
    assert runner.advance(999) == []

    with pytest.raises(ValueError, match="delta_ms"):
        runner.advance(cast(int, delta_ms))

    assert runner.elapsed_ms == 999
    assert runner.advance(1) == [PilotId.PILOT_1, PilotId.PILOT_2]


@pytest.mark.parametrize(
    "schedule",
    (
        ((0, PilotId.PILOT_1),),
        ((-1, PilotId.PILOT_1),),
        ((1.5, PilotId.PILOT_1),),
        ((1_000, cast(PilotId, "PILOT_3")),),
        ((1_000, PilotId.PILOT_1), (1_000, PilotId.PILOT_1)),
    ),
)
def test_invalid_schedule_is_rejected_before_runner_state_exists(
    schedule: tuple[tuple[int, PilotId], ...],
) -> None:
    with pytest.raises(ValueError, match="scheduled|duplicate"):
        ScenarioRunner(_definition(schedule))


def test_runner_instances_and_reset_replacement_are_isolated() -> None:
    definition = get_scenario("single_pilot_unresponsive")
    active = ScenarioRunner(definition)
    independent = ScenarioRunner(definition)

    assert active.advance(2_000) == [
        PilotId.PILOT_1,
        PilotId.PILOT_2,
        PilotId.PILOT_1,
        PilotId.PILOT_2,
    ]
    assert independent.advance(1_000) == [PilotId.PILOT_1, PilotId.PILOT_2]

    reset = ScenarioRunner(get_scenario("single_pilot_unresponsive"))
    assert reset.advance(999) == []
    assert reset.advance(1) == [PilotId.PILOT_1, PilotId.PILOT_2]


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_each_scenario_reset_before_and_after_events_replays_the_same_schedule(
    scenario_id: str,
) -> None:
    expected = [PilotId.PILOT_1, PilotId.PILOT_2, PilotId.PILOT_1, PilotId.PILOT_2]

    before_boundary = ScenarioRunner(get_scenario(scenario_id))
    assert before_boundary.advance(500) == []
    reset_before_event = ScenarioRunner(get_scenario(scenario_id))
    assert reset_before_event.advance(2_000) == expected

    completed = ScenarioRunner(get_scenario(scenario_id))
    assert completed.advance(600_000) == expected
    assert completed.advance(600_000) == []
    reset_after_completion = ScenarioRunner(get_scenario(scenario_id))
    assert reset_after_completion.advance(2_000) == expected


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_scenario_observation_progression_is_repeatable(scenario_id: str) -> None:
    assert _observations(scenario_id) == _observations(scenario_id)
    assert len(_observations(scenario_id)) == 4


def test_normal_flight_observations_remain_responsive() -> None:
    observed = _observations("normal_flight")
    assert {item[2] for item in observed} == {PilotObservationStatus.RESPONSIVE}


def test_single_pilot_scenario_preserves_responsive_peer() -> None:
    observed = _observations("single_pilot_unresponsive")
    statuses = {(pilot_id, status) for _, pilot_id, status, _, _ in observed}
    assert statuses == {
        (PilotId.PILOT_1, PilotObservationStatus.POSSIBLY_UNRESPONSIVE),
        (PilotId.PILOT_2, PilotObservationStatus.RESPONSIVE),
    }


@pytest.mark.parametrize(
    ("scenario_id", "atc_connected"),
    (("dual_pilot_atc_connected", True), ("dual_pilot_atc_disconnected", False)),
)
def test_dual_pilot_scenarios_schedule_concerns_without_authorization(
    scenario_id: str, atc_connected: bool
) -> None:
    definition = get_scenario(scenario_id)
    observed = _observations(scenario_id)

    assert definition.atc_connected is atc_connected
    assert {item[2] for item in observed} == {PilotObservationStatus.POSSIBLY_UNRESPONSIVE}

    simulator = MockAircraftSimulator()
    simulator.start(UUID(int=301), scenario_id, START)
    assert simulator._last_action is None
def test_camera_obstruction_remains_unknown_and_unavailable() -> None:
    observed = _observations("camera_obstructed")
    assert {item[2] for item in observed} == {PilotObservationStatus.UNKNOWN}
    assert all(not camera_available and not face_visible for _, _, _, camera_available, face_visible in observed)


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_scenario_progression_remains_compatible_with_phase2_telemetry(scenario_id: str) -> None:
    run_id = UUID(int=302)
    runner = ScenarioRunner(get_scenario(scenario_id))
    simulator = MockAircraftSimulator()
    telemetry = simulator.start(run_id, scenario_id, START)

    elapsed_ms = 0
    for delta_ms in (999, 1, 1_000, 600_000):
        elapsed_ms += delta_ms
        runner.advance(delta_ms)
        telemetry = simulator.advance(run_id, START + timedelta(milliseconds=elapsed_ms))
        assert type(telemetry) is AircraftTelemetry
        assert telemetry.simulation_time == START + timedelta(milliseconds=elapsed_ms)

    assert simulator._last_action is None
