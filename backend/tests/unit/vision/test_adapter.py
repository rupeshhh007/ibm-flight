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


def test_observe_handles_source_exception_safely(base_time: datetime) -> None:
    """
    Regression test for Review Item 4:
    Source failures must not crash observe(); must fail-closed as UNKNOWN.
    """
    failing_source = ReplayLandmarkSource()

    def raise_error(pilot_id, t, cfg):
        raise RuntimeError("Camera hardware failure")

    failing_source.set_pilot_generator(PilotId.PILOT_1, raise_error)
    adapter = RealVisionAdapter(source=failing_source)

    obs = adapter.observe(PilotId.PILOT_1, base_time)
    assert obs.observation_status == PilotObservationStatus.UNKNOWN
    assert obs.camera_available is False
    assert obs.face_visible is False
    assert obs.observation_quality == 0.0


def test_config_safeguards_reject_zero_and_invalid_durations() -> None:
    """
    Regression test for Review Item 5:
    Zero-duration settings must be rejected by configuration validation.
    """
    # min_observation_duration_ms < 500
    with pytest.raises(ValueError, match="min_observation_duration_ms must be >= 500"):
        VisionConfig(min_observation_duration_ms=0)

    # min_closed_window_ms < 1000
    with pytest.raises(ValueError, match="min_closed_window_ms must be >= 1000"):
        VisionConfig(min_closed_window_ms=200)

    # min_closed_window_ms < min_observation_duration_ms
    with pytest.raises(ValueError, match="min_closed_window_ms must be >= min_observation_duration_ms"):
        VisionConfig(min_observation_duration_ms=2000, min_closed_window_ms=1500)

    # NaN / Inf in thresholds
    with pytest.raises(ValueError, match="finite number"):
        VisionConfig(min_usable_quality=float("nan"))

