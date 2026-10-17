"""
Unit tests for RealVisionAdapter protocol conformance, pilot separation, and integration.

SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
"""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.contracts.enums import PilotId, PilotObservationStatus
from app.contracts.interfaces import VisionAdapter
from app.contracts.models import PilotObservation
from app.modules.vision.adapter import RealVisionAdapter
from app.modules.vision.config import NormalizedROI, PilotChannelConfig, VisionConfig
from app.modules.vision.evidence import PilotFrameEvidence
from app.modules.vision.sources import ReplayLandmarkSource


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_real_vision_adapter_conforms_to_protocol() -> None:
    adapter = RealVisionAdapter()
    assert isinstance(adapter, VisionAdapter)


def test_observe_returns_valid_canonical_pilot_observation(base_time: datetime) -> None:
    adapter = RealVisionAdapter()
    obs = adapter.observe(PilotId.PILOT_1, base_time)
    assert isinstance(obs, PilotObservation)
    assert obs.pilot_id == PilotId.PILOT_1
    assert obs.observed_at == base_time
    assert obs.observation_status in {
        PilotObservationStatus.RESPONSIVE,
        PilotObservationStatus.POSSIBLY_UNRESPONSIVE,
        PilotObservationStatus.UNKNOWN,
    }
    assert 0 <= obs.observation_duration_ms <= 600_000
    assert 0.0 <= obs.observation_quality <= 1.0


def test_canonical_model_rejects_extra_fields(base_time: datetime) -> None:
    with pytest.raises(ValidationError):
        PilotObservation(
            pilot_id=PilotId.PILOT_1,
            observed_at=base_time,
            observation_status=PilotObservationStatus.RESPONSIVE,
            camera_available=True,
            face_visible=True,
            eyes_closed=False,
            observation_duration_ms=1000,
            observation_quality=0.9,
            diagnosis="invalid_extra_field",  # extra="forbid"
        )


def test_timestamp_normalization_naive_datetime() -> None:
    adapter = RealVisionAdapter()
    naive_time = datetime(2026, 1, 1, 12, 0, 0)
    obs = adapter.observe(PilotId.PILOT_1, naive_time)
    assert obs.observed_at.tzinfo == timezone.utc


def test_independent_pilot_channels_no_leakage(base_time: datetime) -> None:
    adapter = RealVisionAdapter()
    # Configure single_pilot_unresponsive where PILOT_1 has closed eyes and PILOT_2 has open eyes
    adapter.configure_scenario("single_pilot_unresponsive")

    # Advance several steps to accumulate duration
    for i in range(7):
        t = base_time + timedelta(milliseconds=i * 500)
        obs1 = adapter.observe(PilotId.PILOT_1, t)
        obs2 = adapter.observe(PilotId.PILOT_2, t)

    t_eval = base_time + timedelta(milliseconds=3000)
    obs1 = adapter.observe(PilotId.PILOT_1, t_eval)
    obs2 = adapter.observe(PilotId.PILOT_2, t_eval)

    # PILOT_1 must be POSSIBLY_UNRESPONSIVE
    assert obs1.pilot_id == PilotId.PILOT_1
    assert obs1.observation_status == PilotObservationStatus.POSSIBLY_UNRESPONSIVE
    assert obs1.eyes_closed is True

    # PILOT_2 must be RESPONSIVE
    assert obs2.pilot_id == PilotId.PILOT_2
    assert obs2.observation_status == PilotObservationStatus.RESPONSIVE
    assert obs2.eyes_closed is False


def test_unmonitored_pilot_channel_produces_unknown(base_time: datetime) -> None:
    # Single pilot configuration: only PILOT_1 enabled, PILOT_2 disabled
    config = VisionConfig.single_pilot(PilotId.PILOT_1)
    adapter = RealVisionAdapter(config=config)

    # PILOT_2 observation must be UNKNOWN with camera_available=False
    obs2 = adapter.observe(PilotId.PILOT_2, base_time)
    assert obs2.observation_status == PilotObservationStatus.UNKNOWN
    assert obs2.camera_available is False
    assert obs2.face_visible is False
    assert obs2.observation_quality == 0.0
    assert obs2.observation_duration_ms == 0


def test_configure_scenario_resets_histories(base_time: datetime) -> None:
    adapter = RealVisionAdapter()
    # Build up duration on normal flight
    for i in range(4):
        adapter.observe(PilotId.PILOT_1, base_time + timedelta(milliseconds=i * 500))

    # Reconfigure scenario resets history
    adapter.configure_scenario("camera_obstructed")
    obs = adapter.observe(PilotId.PILOT_1, base_time + timedelta(milliseconds=2000))
    assert obs.observation_status == PilotObservationStatus.UNKNOWN
    assert obs.observation_duration_ms == 0


def test_replayed_identical_inputs_produce_identical_outputs(base_time: datetime) -> None:
    adapter1 = RealVisionAdapter()
    adapter2 = RealVisionAdapter()

    adapter1.configure_scenario("single_pilot_unresponsive")
    adapter2.configure_scenario("single_pilot_unresponsive")

    for i in range(7):
        t = base_time + timedelta(milliseconds=i * 500)
        o1_p1 = adapter1.observe(PilotId.PILOT_1, t)
        o2_p1 = adapter2.observe(PilotId.PILOT_1, t)
        assert o1_p1.observation_status == o2_p1.observation_status
        assert o1_p1.observation_duration_ms == o2_p1.observation_duration_ms
        assert o1_p1.eyes_closed == o2_p1.eyes_closed

        o1_p2 = adapter1.observe(PilotId.PILOT_2, t)
        o2_p2 = adapter2.observe(PilotId.PILOT_2, t)
        assert o1_p2.observation_status == o2_p2.observation_status
        assert o1_p2.observation_duration_ms == o2_p2.observation_duration_ms


def test_overlapping_rois_rejected_at_config_time() -> None:
    # Pilot 1 and Pilot 2 configured with overlapping ROIs on same camera
    with pytest.raises(ValueError, match="ROIs cannot overlap"):
        VisionConfig(
            pilot_channels={
                PilotId.PILOT_1: PilotChannelConfig(
                    pilot_id=PilotId.PILOT_1,
                    camera_index=0,
                    roi=NormalizedROI(0.0, 0.0, 0.6, 1.0),
                ),
                PilotId.PILOT_2: PilotChannelConfig(
                    pilot_id=PilotId.PILOT_2,
                    camera_index=0,
                    roi=NormalizedROI(0.4, 0.0, 1.0, 1.0),
                ),
            }
        )


def test_close_is_idempotent() -> None:
    source = ReplayLandmarkSource()
    adapter = RealVisionAdapter(source=source)
    adapter.close()
    adapter.close()  # No error on repeated close
