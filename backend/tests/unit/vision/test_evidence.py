"""
Unit tests for Vision temporal evidence window and uncertainty policy.

SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.contracts.enums import PilotId, PilotObservationStatus
from app.modules.vision.config import VisionConfig
from app.modules.vision.evidence import PilotEvidenceWindow, PilotFrameEvidence


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def config() -> VisionConfig:
    return VisionConfig(
        min_usable_quality=0.40,
        min_observation_duration_ms=1_000,
        min_closed_window_ms=3_000,
        min_open_window_ms=1_000,
        max_gap_ms=1_500,
    )


def test_empty_window_produces_unknown(base_time: datetime, config: VisionConfig) -> None:
    window = PilotEvidenceWindow()
    obs = window.evaluate(PilotId.PILOT_1, base_time, config)
    assert obs.observation_status == PilotObservationStatus.UNKNOWN
    assert obs.camera_available is False
    assert obs.face_visible is False
    assert obs.observation_duration_ms == 0
    assert obs.observation_quality == 0.0


def test_camera_unavailable_produces_unknown(base_time: datetime, config: VisionConfig) -> None:
    window = PilotEvidenceWindow()
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=base_time,
            monotonic_capture_time=100.0,
            camera_available=False,
            face_visible=False,
            eyes_closed=False,
            ear=None,
            quality=0.0,
            is_usable=False,
            error_reason="device_disconnected",
        )
    )
    obs = window.evaluate(PilotId.PILOT_1, base_time, config)
    assert obs.observation_status == PilotObservationStatus.UNKNOWN
    assert obs.camera_available is False
    assert obs.face_visible is False
    assert obs.observation_quality == 0.0


def test_face_not_visible_produces_unknown(base_time: datetime, config: VisionConfig) -> None:
    window = PilotEvidenceWindow()
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=base_time,
            monotonic_capture_time=100.0,
            camera_available=True,
            face_visible=False,
            eyes_closed=False,
            ear=None,
            quality=0.0,
            is_usable=False,
            error_reason="face_obscured",
        )
    )
    obs = window.evaluate(PilotId.PILOT_1, base_time, config)
    assert obs.observation_status == PilotObservationStatus.UNKNOWN
    assert obs.camera_available is True
    assert obs.face_visible is False
    assert obs.observation_quality == 0.0


def test_low_quality_produces_unknown(base_time: datetime, config: VisionConfig) -> None:
    window = PilotEvidenceWindow()
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=base_time,
            monotonic_capture_time=100.0,
            camera_available=True,
            face_visible=True,
            eyes_closed=False,
            ear=0.30,
            quality=0.25,  # below min_usable_quality (0.40)
            is_usable=False,
            error_reason="low_lighting",
        )
    )
    obs = window.evaluate(PilotId.PILOT_1, base_time, config)
    assert obs.observation_status == PilotObservationStatus.UNKNOWN
    assert obs.camera_available is True
    assert obs.face_visible is True
    assert obs.observation_duration_ms == 0
    assert obs.observation_quality == 0.25


def test_single_frame_closed_eye_is_never_unresponsive(base_time: datetime, config: VisionConfig) -> None:
    window = PilotEvidenceWindow()
    # Add one high-quality sample with closed eyes
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=base_time,
            monotonic_capture_time=100.0,
            camera_available=True,
            face_visible=True,
            eyes_closed=True,
            ear=0.10,
            quality=0.90,
            is_usable=True,
        )
    )
    obs = window.evaluate(PilotId.PILOT_1, base_time, config)
    # Must be UNKNOWN because duration is 0 < min_observation_duration_ms
    assert obs.observation_status == PilotObservationStatus.UNKNOWN
    assert obs.eyes_closed is True
    assert obs.observation_duration_ms == 0


def test_sustained_closed_eyes_triggers_possibly_unresponsive(
    base_time: datetime, config: VisionConfig
) -> None:
    window = PilotEvidenceWindow()
    # Feed 7 samples at 500 ms intervals = 3000 ms of contiguous closure
    for i in range(7):
        t = base_time + timedelta(milliseconds=i * 500)
        window.add_sample(
            PilotFrameEvidence(
                virtual_time=t,
                monotonic_capture_time=100.0 + i * 0.5,
                camera_available=True,
                face_visible=True,
                eyes_closed=True,
                ear=0.12,
                quality=0.92,
                is_usable=True,
            )
        )

    eval_time = base_time + timedelta(milliseconds=3000)
    obs = window.evaluate(PilotId.PILOT_1, eval_time, config)
    assert obs.observation_status == PilotObservationStatus.POSSIBLY_UNRESPONSIVE
    assert obs.observation_duration_ms == 3000
    assert obs.eyes_closed is True
    assert obs.observation_quality >= 0.90


def test_below_threshold_closed_window_does_not_trigger_unresponsive(
    base_time: datetime, config: VisionConfig
) -> None:
    window = PilotEvidenceWindow()
    # Feed 4 samples at 500 ms intervals = 1500 ms (>= min_obs_duration 1000, but < min_closed_window 3000)
    for i in range(4):
        t = base_time + timedelta(milliseconds=i * 500)
        window.add_sample(
            PilotFrameEvidence(
                virtual_time=t,
                monotonic_capture_time=100.0 + i * 0.5,
                camera_available=True,
                face_visible=True,
                eyes_closed=True,
                ear=0.12,
                quality=0.92,
                is_usable=True,
            )
        )

    eval_time = base_time + timedelta(milliseconds=1500)
    obs = window.evaluate(PilotId.PILOT_1, eval_time, config)
    # Must NOT be POSSIBLY_UNRESPONSIVE yet
    assert obs.observation_status == PilotObservationStatus.UNKNOWN
    assert obs.observation_duration_ms == 1500
    assert obs.eyes_closed is True


def test_sustained_open_eyes_triggers_responsive(base_time: datetime, config: VisionConfig) -> None:
    window = PilotEvidenceWindow()
    # Feed 3 samples at 500 ms intervals = 1000 ms (>= min_open_window 1000)
    for i in range(3):
        t = base_time + timedelta(milliseconds=i * 500)
        window.add_sample(
            PilotFrameEvidence(
                virtual_time=t,
                monotonic_capture_time=100.0 + i * 0.5,
                camera_available=True,
                face_visible=True,
                eyes_closed=False,
                ear=0.32,
                quality=0.95,
                is_usable=True,
            )
        )

    eval_time = base_time + timedelta(milliseconds=1000)
    obs = window.evaluate(PilotId.PILOT_1, eval_time, config)
    assert obs.observation_status == PilotObservationStatus.RESPONSIVE
    assert obs.observation_duration_ms == 1000
    assert obs.eyes_closed is False


def test_intermittent_invalid_frame_resets_accumulated_concern(
    base_time: datetime, config: VisionConfig
) -> None:
    window = PilotEvidenceWindow()
    # 4 valid closed frames (1500 ms)
    for i in range(4):
        t = base_time + timedelta(milliseconds=i * 500)
        window.add_sample(
            PilotFrameEvidence(
                virtual_time=t,
                monotonic_capture_time=100.0 + i * 0.5,
                camera_available=True,
                face_visible=True,
                eyes_closed=True,
                ear=0.12,
                quality=0.92,
                is_usable=True,
            )
        )

    # 1 invalid frame (camera obstructed / face hidden)
    t_invalid = base_time + timedelta(milliseconds=2000)
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=t_invalid,
            monotonic_capture_time=102.0,
            camera_available=True,
            face_visible=False,
            eyes_closed=False,
            ear=None,
            quality=0.0,
            is_usable=False,
            error_reason="obstruction",
        )
    )

    # Observation right after obstruction is UNKNOWN with 0 duration
    obs = window.evaluate(PilotId.PILOT_1, t_invalid, config)
    assert obs.observation_status == PilotObservationStatus.UNKNOWN
    assert obs.observation_duration_ms == 0

    # 1 subsequent closed frame should start fresh from duration 0, not accumulate past obstruction
    t_resume = base_time + timedelta(milliseconds=2500)
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=t_resume,
            monotonic_capture_time=102.5,
            camera_available=True,
            face_visible=True,
            eyes_closed=True,
            ear=0.12,
            quality=0.92,
            is_usable=True,
        )
    )
    obs_resume = window.evaluate(PilotId.PILOT_1, t_resume, config)
    assert obs_resume.observation_status == PilotObservationStatus.UNKNOWN
    assert obs_resume.observation_duration_ms == 0  # Only 1 sample in new contiguous chain


def test_temporal_gap_breaks_contiguous_duration(base_time: datetime, config: VisionConfig) -> None:
    window = PilotEvidenceWindow()
    # 2 valid frames at 0 ms and 500 ms
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=base_time,
            monotonic_capture_time=100.0,
            camera_available=True,
            face_visible=True,
            eyes_closed=True,
            ear=0.12,
            quality=0.92,
            is_usable=True,
        )
    )
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=base_time + timedelta(milliseconds=500),
            monotonic_capture_time=100.5,
            camera_available=True,
            face_visible=True,
            eyes_closed=True,
            ear=0.12,
            quality=0.92,
            is_usable=True,
        )
    )

    # Next frame comes after 2500 ms gap (exceeds max_gap_ms = 1500 ms)
    t_after_gap = base_time + timedelta(milliseconds=3000)
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=t_after_gap,
            monotonic_capture_time=103.0,
            camera_available=True,
            face_visible=True,
            eyes_closed=True,
            ear=0.12,
            quality=0.92,
            is_usable=True,
        )
    )

    obs = window.evaluate(PilotId.PILOT_1, t_after_gap, config)
    # The chain broke before t_after_gap, so contiguous duration is 0
    assert obs.observation_duration_ms == 0


def test_recovery_from_unresponsive_to_responsive(base_time: datetime, config: VisionConfig) -> None:
    window = PilotEvidenceWindow()
    # Sustained closed for 3000 ms (7 frames)
    for i in range(7):
        t = base_time + timedelta(milliseconds=i * 500)
        window.add_sample(
            PilotFrameEvidence(
                virtual_time=t,
                monotonic_capture_time=100.0 + i * 0.5,
                camera_available=True,
                face_visible=True,
                eyes_closed=True,
                ear=0.12,
                quality=0.92,
                is_usable=True,
            )
        )
    assert window.evaluate(PilotId.PILOT_1, base_time + timedelta(milliseconds=3000), config).observation_status == PilotObservationStatus.POSSIBLY_UNRESPONSIVE

    # Pilot reopens eyes: add 3 open frames across 1000 ms
    for i in range(1, 4):
        t = base_time + timedelta(milliseconds=3000 + i * 500)
        window.add_sample(
            PilotFrameEvidence(
                virtual_time=t,
                monotonic_capture_time=103.0 + i * 0.5,
                camera_available=True,
                face_visible=True,
                eyes_closed=False,
                ear=0.32,
                quality=0.95,
                is_usable=True,
            )
        )

    # After 1000 ms of open eyes, status recovers to RESPONSIVE
    t_recovered = base_time + timedelta(milliseconds=4500)
    obs = window.evaluate(PilotId.PILOT_1, t_recovered, config)
    assert obs.observation_status == PilotObservationStatus.RESPONSIVE
    assert obs.eyes_closed is False


def test_reset_clears_window(base_time: datetime, config: VisionConfig) -> None:
    window = PilotEvidenceWindow()
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=base_time,
            monotonic_capture_time=100.0,
            camera_available=True,
            face_visible=True,
            eyes_closed=False,
            ear=0.32,
            quality=0.95,
            is_usable=True,
        )
    )
    assert window.latest_sample is not None
    window.reset()
    assert window.latest_sample is None
