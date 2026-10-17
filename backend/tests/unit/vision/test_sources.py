"""
Unit tests for Vision sources: ReplayLandmarkSource and optional OpenCVCaptureSource.

SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.contracts.enums import PilotId
from app.modules.vision.config import VisionConfig
from app.modules.vision.evidence import PilotFrameEvidence
from app.modules.vision.sources import (
    OpenCVCaptureSource,
    ReplayLandmarkSource,
    create_synthetic_landmarks,
    is_mediapipe_available,
    is_opencv_available,
)


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def config() -> VisionConfig:
    return VisionConfig()


def test_synthetic_landmarks_creation() -> None:
    landmarks_open = create_synthetic_landmarks(ear=0.30)
    assert len(landmarks_open) == 468
    assert all(p.in_bounds() for p in landmarks_open)

    landmarks_closed = create_synthetic_landmarks(ear=0.08)
    assert len(landmarks_closed) == 468


def test_replay_source_default_scenarios(base_time: datetime, config: VisionConfig) -> None:
    source = ReplayLandmarkSource()

    # normal_flight: both open
    source.configure_scenario("normal_flight")
    s1 = source.get_sample(PilotId.PILOT_1, base_time, config)
    s2 = source.get_sample(PilotId.PILOT_2, base_time, config)
    assert s1.eyes_closed is False
    assert s2.eyes_closed is False
    assert s1.camera_available is True
    assert s2.camera_available is True

    # camera_obstructed: camera unavailable
    source.configure_scenario("camera_obstructed")
    s_obs = source.get_sample(PilotId.PILOT_1, base_time, config)
    assert s_obs.camera_available is False
    assert s_obs.face_visible is False
    assert s_obs.is_usable is False

    # single_pilot_unresponsive: P1 closed, P2 open
    source.configure_scenario("single_pilot_unresponsive")
    s_p1 = source.get_sample(PilotId.PILOT_1, base_time, config)
    s_p2 = source.get_sample(PilotId.PILOT_2, base_time, config)
    assert s_p1.eyes_closed is True
    assert s_p2.eyes_closed is False

    # dual_pilot_atc_connected: both closed
    source.configure_scenario("dual_pilot_atc_connected")
    assert source.get_sample(PilotId.PILOT_1, base_time, config).eyes_closed is True
    assert source.get_sample(PilotId.PILOT_2, base_time, config).eyes_closed is True


def test_replay_source_custom_track(base_time: datetime, config: VisionConfig) -> None:
    source = ReplayLandmarkSource()
    custom_sample = PilotFrameEvidence(
        virtual_time=base_time,
        monotonic_capture_time=1.0,
        camera_available=True,
        face_visible=True,
        eyes_closed=True,
        ear=0.10,
        quality=0.88,
        is_usable=True,
    )
    source.set_pilot_track(PilotId.PILOT_1, [custom_sample])
    sample = source.get_sample(PilotId.PILOT_1, base_time, config)
    assert sample == custom_sample


def test_replay_source_custom_generator(base_time: datetime, config: VisionConfig) -> None:
    source = ReplayLandmarkSource()

    def my_generator(pilot_id: PilotId, t: datetime, c: VisionConfig) -> PilotFrameEvidence:
        return PilotFrameEvidence(
            virtual_time=t,
            monotonic_capture_time=42.0,
            camera_available=True,
            face_visible=True,
            eyes_closed=False,
            ear=0.35,
            quality=0.99,
            is_usable=True,
        )

    source.set_pilot_generator(PilotId.PILOT_1, my_generator)
    sample = source.get_sample(PilotId.PILOT_1, base_time, config)
    assert sample.quality == 0.99
    assert sample.monotonic_capture_time == 42.0


def test_replay_source_close(base_time: datetime, config: VisionConfig) -> None:
    source = ReplayLandmarkSource()
    source.close()
    sample = source.get_sample(PilotId.PILOT_1, base_time, config)
    assert sample.camera_available is False
    assert sample.is_usable is False
    assert sample.error_reason == "source_closed"


def test_opencv_capture_source_missing_dependency() -> None:
    with patch("app.modules.vision.sources.is_opencv_available", return_value=False):
        with pytest.raises(RuntimeError, match="OpenCV .* is not installed"):
            OpenCVCaptureSource(0)
