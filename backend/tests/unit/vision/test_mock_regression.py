"""
Regression tests verifying MockVisionAdapter preserves 100% of P0 behavior across all scenarios.

SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
"""

from datetime import datetime, timezone

import pytest

from app.contracts.enums import PilotId, PilotObservationStatus
from app.contracts.interfaces import VisionAdapter
from app.modules.vision.mock import MockVisionAdapter


@pytest.fixture
def mock_adapter() -> MockVisionAdapter:
    return MockVisionAdapter()


@pytest.fixture
def timestamp() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_mock_adapter_conforms_to_protocol(mock_adapter: MockVisionAdapter) -> None:
    assert isinstance(mock_adapter, VisionAdapter)


def test_mock_normal_flight(mock_adapter: MockVisionAdapter, timestamp: datetime) -> None:
    mock_adapter.configure_scenario("normal_flight")
    obs1 = mock_adapter.observe(PilotId.PILOT_1, timestamp)
    obs2 = mock_adapter.observe(PilotId.PILOT_2, timestamp)

    assert obs1.observation_status == PilotObservationStatus.RESPONSIVE
    assert obs1.camera_available is True
    assert obs1.face_visible is True
    assert obs1.eyes_closed is False
    assert obs1.observation_quality == pytest.approx(0.95)

    assert obs2.observation_status == PilotObservationStatus.RESPONSIVE
    assert obs2.camera_available is True
    assert obs2.face_visible is True
    assert obs2.eyes_closed is False
    assert obs2.observation_quality == pytest.approx(0.95)


def test_mock_single_pilot_unresponsive(mock_adapter: MockVisionAdapter, timestamp: datetime) -> None:
    mock_adapter.configure_scenario("single_pilot_unresponsive")
    obs1 = mock_adapter.observe(PilotId.PILOT_1, timestamp)
    obs2 = mock_adapter.observe(PilotId.PILOT_2, timestamp)

    # PILOT_1 has concern
    assert obs1.observation_status == PilotObservationStatus.POSSIBLY_UNRESPONSIVE
    assert obs1.eyes_closed is True
    assert obs1.observation_quality == pytest.approx(0.90)

    # PILOT_2 is responsive
    assert obs2.observation_status == PilotObservationStatus.RESPONSIVE
    assert obs2.eyes_closed is False
    assert obs2.observation_quality == pytest.approx(0.95)


def test_mock_dual_pilot_emergencies(mock_adapter: MockVisionAdapter, timestamp: datetime) -> None:
    for scenario in ("dual_pilot_atc_connected", "dual_pilot_atc_disconnected"):
        mock_adapter.configure_scenario(scenario)
        obs1 = mock_adapter.observe(PilotId.PILOT_1, timestamp)
        obs2 = mock_adapter.observe(PilotId.PILOT_2, timestamp)

        assert obs1.observation_status == PilotObservationStatus.POSSIBLY_UNRESPONSIVE
        assert obs1.eyes_closed is True
        assert obs1.observation_quality == pytest.approx(0.90)

        assert obs2.observation_status == PilotObservationStatus.POSSIBLY_UNRESPONSIVE
        assert obs2.eyes_closed is True
        assert obs2.observation_quality == pytest.approx(0.90)


def test_mock_camera_obstructed(mock_adapter: MockVisionAdapter, timestamp: datetime) -> None:
    mock_adapter.configure_scenario("camera_obstructed")
    obs1 = mock_adapter.observe(PilotId.PILOT_1, timestamp)
    obs2 = mock_adapter.observe(PilotId.PILOT_2, timestamp)

    for obs in (obs1, obs2):
        assert obs.observation_status == PilotObservationStatus.UNKNOWN
        assert obs.camera_available is False
        assert obs.face_visible is False
        assert obs.observation_quality == 0.0
