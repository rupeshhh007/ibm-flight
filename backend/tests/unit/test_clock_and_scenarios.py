from datetime import datetime, timezone

import pytest

from app.contracts.enums import PilotId
from app.core.clock import VirtualClock
from app.scenarios.catalog import get_scenario, list_scenarios
from app.scenarios.runner import ScenarioRunner


def test_catalog_has_exactly_five_stable_ids() -> None:
    assert [item.scenario_id for item in list_scenarios()] == [
        "normal_flight",
        "single_pilot_unresponsive",
        "dual_pilot_atc_connected",
        "dual_pilot_atc_disconnected",
        "camera_obstructed",
    ]


def test_virtual_clock_and_boundary_events_advance_once_without_sleep() -> None:
    clock = VirtualClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    runner = ScenarioRunner(get_scenario("normal_flight"))
    assert runner.advance(999) == []
    clock.advance(999)
    assert runner.advance(1) == [PilotId.PILOT_1, PilotId.PILOT_2]
    assert runner.advance(1) == []
    assert clock.now().isoformat() == "2026-01-01T00:00:00.999000+00:00"
    with pytest.raises(ValueError):
        clock.advance(0)
