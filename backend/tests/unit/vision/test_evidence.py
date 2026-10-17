"""
Unit tests for Vision temporal evidence window and uncertainty policy.

SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.contracts.enums import PilotId, PilotObservationStatus
from app.modules.vision.config import PilotChannelConfig, VisionConfig
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


def test_out_of_order_samples_are_rejected(base_time: datetime, config: VisionConfig) -> None:
    """Regression test for Review Item 3: Out-of-order samples must not corrupt timeline."""
    window = PilotEvidenceWindow()
    t1 = base_time
    t2 = base_time + timedelta(milliseconds=500)
    t_stale = base_time - timedelta(milliseconds=500)  # Earlier than t1

    window.add_sample(
        PilotFrameEvidence(
            virtual_time=t1,
            monotonic_capture_time=100.0,
            camera_available=True,
            face_visible=True,
            eyes_closed=False,
            ear=0.32,
            quality=0.95,
            is_usable=True,
        )
    )
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=t2,
            monotonic_capture_time=100.5,
            camera_available=True,
            face_visible=True,
            eyes_closed=False,
            ear=0.32,
            quality=0.95,
            is_usable=True,
        )
    )

    # Attempt to add an out-of-order sample
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=t_stale,
            monotonic_capture_time=99.0,
            camera_available=True,
            face_visible=True,
            eyes_closed=True,
            ear=0.10,
            quality=0.90,
            is_usable=True,
        )
    )

    # Out of order sample must reset the window to avoid stale/corrupted history leakage
    assert window.latest_sample is None


def test_repeated_duplicate_samples_do_not_inflate_duration(
    base_time: datetime, config: VisionConfig
) -> None:
    """
    Regression test for Review Item 3:
    Repeated observations at the exact same timestamp must not inflate sample count or duration.
    """
    window = PilotEvidenceWindow()
    # Add 10 duplicate samples at the exact same timestamp
    for _ in range(10):
        window.add_sample(
            PilotFrameEvidence(
                virtual_time=base_time,
                monotonic_capture_time=100.0,
                camera_available=True,
                face_visible=True,
                eyes_closed=True,
                ear=0.10,
                quality=0.95,
                is_usable=True,
            )
        )

    # Window should deduplicate in place; sample count in deque should be 1
    assert len(window._samples) == 1
    obs = window.evaluate(PilotId.PILOT_1, base_time, config)
    # Single timestamp cannot produce duration or POSSIBLY_UNRESPONSIVE
    assert obs.observation_duration_ms == 0
    assert obs.observation_status == PilotObservationStatus.UNKNOWN


def test_future_samples_relative_to_observed_at_are_excluded(
    base_time: datetime, config: VisionConfig
) -> None:
    """Regression test for Review Item 3: Future samples relative to observed_at are excluded."""
    window = PilotEvidenceWindow()
    t_past = base_time
    t_future = base_time + timedelta(milliseconds=5000)

    window.add_sample(
        PilotFrameEvidence(
            virtual_time=t_past,
            monotonic_capture_time=100.0,
            camera_available=True,
            face_visible=True,
            eyes_closed=False,
            ear=0.30,
            quality=0.90,
            is_usable=True,
        )
    )
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=t_future,
            monotonic_capture_time=105.0,
            camera_available=True,
            face_visible=True,
            eyes_closed=True,
            ear=0.10,
            quality=0.90,
            is_usable=True,
        )
    )

    # Evaluating at base_time should NOT see the future sample
    obs = window.evaluate(PilotId.PILOT_1, base_time, config)
    assert obs.eyes_closed is False


def test_nan_and_inf_quality_handled_safely(base_time: datetime, config: VisionConfig) -> None:
    """Regression test for Review Item 4: NaN and Inf quality values must yield UNKNOWN."""
    # NaN quality
    sample_nan = PilotFrameEvidence(
        virtual_time=base_time,
        monotonic_capture_time=100.0,
        camera_available=True,
        face_visible=True,
        eyes_closed=False,
        ear=0.30,
        quality=float("nan"),
        is_usable=True,
    )
    assert sample_nan.quality == 0.0
    assert sample_nan.is_usable is False

    window = PilotEvidenceWindow()
    window.add_sample(sample_nan)
    obs = window.evaluate(PilotId.PILOT_1, base_time, config)
    assert obs.observation_status == PilotObservationStatus.UNKNOWN
    assert obs.observation_quality == 0.0


def test_naive_virtual_time_normalized_by_pilot_frame_evidence() -> None:
    """Regression test: Naive virtual_time is safely normalized to UTC."""
    naive_dt = datetime(2026, 1, 1, 12, 0, 0)
    pfe = PilotFrameEvidence(
        virtual_time=naive_dt,
        monotonic_capture_time=100.0,
        camera_available=True,
        face_visible=True,
        eyes_closed=False,
        ear=0.30,
        quality=0.90,
        is_usable=True,
    )
    assert pfe.virtual_time.tzinfo == timezone.utc


def test_evidence_window_rejects_brief_20ms_closed_eyes_after_long_open(base_time: datetime, config: VisionConfig) -> None:
    """
    Regression test for Re-review Item 3:
    POSSIBLY_UNRESPONSIVE reproduced after only 20 ms of closed-eye evidence.
    The closed-eye condition must independently satisfy min_closed_window_ms (3000ms),
    not rely on earlier open-eye history duration.
    """
    window = PilotEvidenceWindow()
    # 5 seconds of sustained open eyes (10 samples, 500ms apart)
    for i in range(11):
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

    # Now add 2 closed samples spanning only 20 ms (e.g. at 5010ms and 5020ms)
    t_closed_1 = base_time + timedelta(milliseconds=5010)
    t_closed_2 = base_time + timedelta(milliseconds=5020)
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=t_closed_1,
            monotonic_capture_time=105.01,
            camera_available=True,
            face_visible=True,
            eyes_closed=True,
            ear=0.10,
            quality=0.95,
            is_usable=True,
        )
    )
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=t_closed_2,
            monotonic_capture_time=105.02,
            camera_available=True,
            face_visible=True,
            eyes_closed=True,
            ear=0.10,
            quality=0.95,
            is_usable=True,
        )
    )

    # Evaluating at 5020ms: closed evidence only spans 20ms (< 3000ms).
    # MUST NOT emit POSSIBLY_UNRESPONSIVE! Must safely return UNKNOWN.
    obs = window.evaluate(PilotId.PILOT_1, t_closed_2, config)
    assert obs.observation_status == PilotObservationStatus.UNKNOWN


def test_evidence_window_rejects_brief_1ms_open_eyes_after_long_closed(base_time: datetime, config: VisionConfig) -> None:
    """
    Regression test for Re-review Item 3:
    RESPONSIVE reproduced after only 1 ms of open-eye evidence.
    The open-eye condition must independently satisfy min_open_window_ms (1000ms).
    """
    window = PilotEvidenceWindow()
    # 5 seconds of sustained closed eyes (11 samples, 500ms apart)
    for i in range(11):
        t = base_time + timedelta(milliseconds=i * 500)
        window.add_sample(
            PilotFrameEvidence(
                virtual_time=t,
                monotonic_capture_time=100.0 + i * 0.5,
                camera_available=True,
                face_visible=True,
                eyes_closed=True,
                ear=0.08,
                quality=0.95,
                is_usable=True,
            )
        )

    # Now add 2 open samples spanning only 1 ms (at 5001ms and 5002ms)
    t_open_1 = base_time + timedelta(milliseconds=5001)
    t_open_2 = base_time + timedelta(milliseconds=5002)
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=t_open_1,
            monotonic_capture_time=105.001,
            camera_available=True,
            face_visible=True,
            eyes_closed=False,
            ear=0.30,
            quality=0.95,
            is_usable=True,
        )
    )
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=t_open_2,
            monotonic_capture_time=105.002,
            camera_available=True,
            face_visible=True,
            eyes_closed=False,
            ear=0.30,
            quality=0.95,
            is_usable=True,
        )
    )

    # Evaluating at 5002ms: open evidence only spans 1ms (< 1000ms).
    # MUST NOT emit RESPONSIVE! Must safely return UNKNOWN.
    obs = window.evaluate(PilotId.PILOT_1, t_open_2, config)
    assert obs.observation_status == PilotObservationStatus.UNKNOWN


def test_evidence_window_ambiguous_ear_stays_unknown(base_time: datetime, config: VisionConfig) -> None:
    """
    Regression test for Re-review Item 5:
    Ambiguous EAR (e.g. 0.22, between closed threshold 0.20 and open threshold 0.25)
    must NOT be treated as open-eye evidence.
    """
    window = PilotEvidenceWindow()
    # Feed 2 seconds of ambiguous samples (EAR=0.22)
    for i in range(5):
        t = base_time + timedelta(milliseconds=i * 500)
        window.add_sample(
            PilotFrameEvidence(
                virtual_time=t,
                monotonic_capture_time=100.0 + i * 0.5,
                camera_available=True,
                face_visible=True,
                eyes_closed=False,
                ear=0.22,  # Ambiguous!
                quality=0.95,
                is_usable=True,
            )
        )

    obs = window.evaluate(PilotId.PILOT_1, base_time + timedelta(milliseconds=2000), config)
    assert obs.observation_status == PilotObservationStatus.UNKNOWN


def test_evidence_window_out_of_order_resets_window(base_time: datetime, config: VisionConfig) -> None:
    """Regression test for Re-review Item 4: out of order sample resets window to avoid leakage."""
    window = PilotEvidenceWindow()
    t1 = base_time + timedelta(seconds=1)
    t2 = base_time + timedelta(seconds=2)
    t_past = base_time + timedelta(milliseconds=500)

    window.add_sample(
        PilotFrameEvidence(
            virtual_time=t1,
            monotonic_capture_time=100.0,
            camera_available=True,
            face_visible=True,
            eyes_closed=False,
            ear=0.30,
            quality=0.90,
            is_usable=True,
        )
    )
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=t2,
            monotonic_capture_time=101.0,
            camera_available=True,
            face_visible=True,
            eyes_closed=False,
            ear=0.30,
            quality=0.90,
            is_usable=True,
        )
    )
    assert len(window._samples) == 2

    # Out of order sample
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=t_past,
            monotonic_capture_time=102.0,
            camera_available=True,
            face_visible=True,
            eyes_closed=False,
            ear=0.30,
            quality=0.90,
            is_usable=True,
        )
    )
    # Window must be reset to avoid corrupted timeline
    assert len(window._samples) == 0


def test_pilot_frame_evidence_rejects_quality_greater_than_one_and_invalid_ear(base_time: datetime) -> None:
    """Regression test for Re-review Item 5: Quality > 1 and invalid EAR rejected."""
    # Quality > 1.0
    pfe_q = PilotFrameEvidence(
        virtual_time=base_time,
        monotonic_capture_time=100.0,
        camera_available=True,
        face_visible=True,
        eyes_closed=False,
        ear=0.30,
        quality=1.5,
        is_usable=True,
    )
    assert pfe_q.quality == 0.0
    assert pfe_q.is_usable is False
    assert pfe_q.error_reason == "invalid_numeric_quality"

    # EAR > 1.0
    pfe_ear = PilotFrameEvidence(
        virtual_time=base_time,
        monotonic_capture_time=100.0,
        camera_available=True,
        face_visible=True,
        eyes_closed=False,
        ear=2.5,
        quality=0.90,
        is_usable=True,
    )
    assert pfe_ear.ear is None
    assert pfe_ear.is_usable is False
    assert pfe_ear.error_reason == "invalid_numeric_ear"


def test_config_rejects_non_finite_temporal_settings() -> None:
    """Regression test for Re-review Item 5: nonfinite temporal settings rejected."""
    with pytest.raises(ValueError, match="finite number"):
        VisionConfig(min_closed_window_ms=float("nan"))  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="finite number"):
        VisionConfig(max_gap_ms=float("inf"))  # type: ignore[arg-type]


def test_config_requires_rois_when_pilots_share_source() -> None:
    """
    Regression test for Re-review Item 2:
    Pilots sharing a source without explicit ROIs must be rejected.
    """
    with pytest.raises(ValueError, match="both pilots MUST have explicit, disjoint non-overlapping ROIs"):
        VisionConfig(
            pilot_channels={
                PilotId.PILOT_1: PilotChannelConfig(pilot_id=PilotId.PILOT_1, camera_index=0, roi=None, enabled=True),
                PilotId.PILOT_2: PilotChannelConfig(pilot_id=PilotId.PILOT_2, camera_index=0, roi=None, enabled=True),
            }
        )


# =====================================================================
# Review Finding Regressions: Evidence Integrity & Precision
# =====================================================================

def test_missing_ear_fails_closed_cannot_become_possibly_unresponsive(
    base_time: datetime,
    config: VisionConfig,
) -> None:
    """
    P1 Regression Test:
    Missing EAR (ear=None) must independently fail closed.
    Even with eyes_closed=True, quality=0.95, and usable-looking frames repeated
    over 4.5 seconds, the evidence window must NEVER produce POSSIBLY_UNRESPONSIVE.
    """
    # 1. PilotFrameEvidence.__post_init__ fails closed if eyes_closed=True with ear=None
    pfe = PilotFrameEvidence(
        virtual_time=base_time,
        monotonic_capture_time=100.0,
        camera_available=True,
        face_visible=True,
        eyes_closed=True,
        ear=None,
        quality=0.95,
        is_usable=True,
    )
    assert pfe.is_usable is False
    assert pfe.error_reason == "missing_eye_geometry"

    # 2. A window of repeated usable-looking frames where ear=None cannot become POSSIBLY_UNRESPONSIVE
    window_natural = PilotEvidenceWindow()
    for i in range(10):
        t = base_time + timedelta(milliseconds=i * 500)
        window_natural.add_sample(
            PilotFrameEvidence(
                virtual_time=t,
                monotonic_capture_time=100.0 + i * 0.5,
                camera_available=True,
                face_visible=True,
                eyes_closed=True,
                ear=None,
                quality=0.95,
                is_usable=True,
                frame_id=i + 1,
            )
        )
    eval_time = base_time + timedelta(milliseconds=4500)
    obs_natural = window_natural.evaluate(PilotId.PILOT_1, eval_time, config)
    assert obs_natural.observation_status == PilotObservationStatus.UNKNOWN
    assert obs_natural.observation_status != PilotObservationStatus.POSSIBLY_UNRESPONSIVE
    assert obs_natural.eyes_closed is False
    assert obs_natural.observation_duration_ms == 0

    # 3. Even if someone forcibly overrides is_usable=True into the window,
    # the evaluator's closed_run independently rejects ear=None and refuses to trigger POSSIBLY_UNRESPONSIVE.
    window_forced = PilotEvidenceWindow()
    for i in range(10):
        t = base_time + timedelta(milliseconds=i * 500)
        sample = PilotFrameEvidence(
            virtual_time=t,
            monotonic_capture_time=100.0 + i * 0.5,
            camera_available=True,
            face_visible=True,
            eyes_closed=True,
            ear=None,
            quality=0.95,
            is_usable=True,
            frame_id=i + 1,
        )
        object.__setattr__(sample, "is_usable", True)
        window_forced.add_sample(sample)

    obs_forced = window_forced.evaluate(PilotId.PILOT_1, eval_time, config)
    assert obs_forced.observation_status == PilotObservationStatus.UNKNOWN
    assert obs_forced.observation_status != PilotObservationStatus.POSSIBLY_UNRESPONSIVE
    assert obs_forced.eyes_closed is False


def test_physical_frame_reuse_cannot_accumulate_temporal_duration(
    base_time: datetime,
    config: VisionConfig,
) -> None:
    """
    P1 Regression Test:
    A single physical frame reused across several virtual timestamps spanning 5 seconds
    must NOT accumulate independent temporal duration or trigger POSSIBLY_UNRESPONSIVE.
    """
    window = PilotEvidenceWindow()
    # Physical frame captured once at monotonic time 100.0 with frame_id=101
    static_frame_id = 101
    static_mono = 100.0

    # Virtual time advances by 1 second each step across 6 observations (0s to 5s)
    for i in range(6):
        t = base_time + timedelta(seconds=i)
        sample = PilotFrameEvidence(
            virtual_time=t,
            monotonic_capture_time=static_mono,
            camera_available=True,
            face_visible=True,
            eyes_closed=True,
            ear=0.12,
            quality=0.95,
            is_usable=True,
            frame_id=static_frame_id,
        )
        window.add_sample(sample)

    eval_time = base_time + timedelta(seconds=5)
    obs = window.evaluate(PilotId.PILOT_1, eval_time, config)

    # The single physical frame represents only 1 instantaneous capture (distinct frames = 1).
    # It must not accumulate 5 seconds of duration or infer sustained eye closure!
    assert obs.observation_status == PilotObservationStatus.UNKNOWN
    assert obs.observation_status != PilotObservationStatus.POSSIBLY_UNRESPONSIVE
    assert obs.observation_duration_ms == 0


def test_distinct_physical_frames_accumulate_temporal_duration(
    base_time: datetime,
    config: VisionConfig,
) -> None:
    """
    Verify that when physical frames DO advance with distinct frame IDs / capture times,
    independent temporal evidence accumulates and triggers POSSIBLY_UNRESPONSIVE after min_closed_window_ms.
    """
    window = PilotEvidenceWindow()
    # 5 distinct physical frames advancing at 1-second intervals (0s to 4s)
    for i in range(5):
        t = base_time + timedelta(seconds=i)
        sample = PilotFrameEvidence(
            virtual_time=t,
            monotonic_capture_time=100.0 + i,
            camera_available=True,
            face_visible=True,
            eyes_closed=True,
            ear=0.12,
            quality=0.95,
            is_usable=True,
            frame_id=i + 1,
        )
        window.add_sample(sample)

    eval_time = base_time + timedelta(seconds=4)
    obs = window.evaluate(PilotId.PILOT_1, eval_time, config)

    assert obs.observation_status == PilotObservationStatus.POSSIBLY_UNRESPONSIVE
    assert obs.observation_duration_ms >= config.min_closed_window_ms
    assert obs.eyes_closed is True


def test_pilot_channels_swapped_id_validation() -> None:
    """
    P2 Regression Test:
    Validate that pilot_channels keys must match each PilotChannelConfig's pilot_id.
    Swapped IDs must be rejected by VisionConfig validation.
    """
    from app.modules.vision.geometry import NormalizedROI

    with pytest.raises(ValueError, match="pilot_channels key .* does not match"):
        VisionConfig(
            pilot_channels={
                PilotId.PILOT_1: PilotChannelConfig(
                    pilot_id=PilotId.PILOT_2,
                    roi=NormalizedROI(0.0, 0.0, 0.5, 1.0),
                    enabled=True,
                ),
                PilotId.PILOT_2: PilotChannelConfig(
                    pilot_id=PilotId.PILOT_1,
                    roi=NormalizedROI(0.5, 0.0, 1.0, 1.0),
                    enabled=True,
                ),
            }
        )


def test_quality_threshold_precision_near_80_and_805(
    base_time: datetime,
    config: VisionConfig,
) -> None:
    """
    P2 Regression Test:
    Avoid rounding raw observation quality upward before Guardian evaluates its minimum evidence-quality threshold.
    Test near 0.80 (e.g. 0.796 does not round up to 0.80) and higher-precision thresholds including 0.805.
    """
    # 1. Raw quality 0.796: in older 2-digit rounding, round(0.796, 2) became 0.80 (rounding upward).
    # With raw precision preserved, 0.796 must stay 0.796 and fail a >= 0.80 threshold.
    window_796 = PilotEvidenceWindow()
    for i in range(5):
        t = base_time + timedelta(seconds=i)
        window_796.add_sample(
            PilotFrameEvidence(
                virtual_time=t,
                monotonic_capture_time=100.0 + i,
                camera_available=True,
                face_visible=True,
                eyes_closed=True,
                ear=0.12,
                quality=0.796,
                is_usable=True,
                frame_id=i + 1,
            )
        )
    obs_796 = window_796.evaluate(PilotId.PILOT_1, base_time + timedelta(seconds=4), config)
    assert obs_796.observation_quality == pytest.approx(0.796, abs=1e-5)
    assert obs_796.observation_quality < 0.80

    # 2. Raw quality 0.804 vs 0.805 threshold:
    window_804 = PilotEvidenceWindow()
    for i in range(5):
        t = base_time + timedelta(seconds=i)
        window_804.add_sample(
            PilotFrameEvidence(
                virtual_time=t,
                monotonic_capture_time=100.0 + i,
                camera_available=True,
                face_visible=True,
                eyes_closed=True,
                ear=0.12,
                quality=0.804,
                is_usable=True,
                frame_id=i + 1,
            )
        )
    obs_804 = window_804.evaluate(PilotId.PILOT_1, base_time + timedelta(seconds=4), config)
    assert obs_804.observation_quality == pytest.approx(0.804, abs=1e-5)
    assert obs_804.observation_quality < 0.805

    # 3. Raw quality 0.805: meets >= 0.805 threshold
    window_805 = PilotEvidenceWindow()
    for i in range(5):
        t = base_time + timedelta(seconds=i)
        window_805.add_sample(
            PilotFrameEvidence(
                virtual_time=t,
                monotonic_capture_time=100.0 + i,
                camera_available=True,
                face_visible=True,
                eyes_closed=True,
                ear=0.12,
                quality=0.805,
                is_usable=True,
                frame_id=i + 1,
            )
        )
    obs_805 = window_805.evaluate(PilotId.PILOT_1, base_time + timedelta(seconds=4), config)
    assert obs_805.observation_quality == pytest.approx(0.805, abs=1e-5)
    assert obs_805.observation_quality >= 0.805


def test_duplicated_physical_frames_do_not_inflate_virtual_evidence_duration(
    base_time: datetime,
    config: VisionConfig,
) -> None:
    """
    Regression test for Issue 2:
    - At virtual 0 ms: frame A, closed eyes.
    - At virtual 100 ms: new frame B, closed eyes.
    - At virtual 1100, 2100, and 3100 ms: reuse physical frame B with same frame ID and capture time.
    Only 100 ms separates distinct physical captures.
    The system must NOT classify this as sustained 3-second eye closure (POSSIBLY_UNRESPONSIVE).
    """
    window = PilotEvidenceWindow()

    # At virtual 0 ms: frame A, closed eyes
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=base_time,
            monotonic_capture_time=100.0,
            camera_available=True,
            face_visible=True,
            eyes_closed=True,
            ear=0.12,
            quality=0.95,
            is_usable=True,
            frame_id="frame_A",
        )
    )

    # At virtual 100 ms: new frame B, closed eyes
    window.add_sample(
        PilotFrameEvidence(
            virtual_time=base_time + timedelta(milliseconds=100),
            monotonic_capture_time=100.1,
            camera_available=True,
            face_visible=True,
            eyes_closed=True,
            ear=0.12,
            quality=0.95,
            is_usable=True,
            frame_id="frame_B",
        )
    )

    # At virtual 1100, 2100, and 3100 ms: reuse physical frame B
    for offset_ms in (1100, 2100, 3100):
        window.add_sample(
            PilotFrameEvidence(
                virtual_time=base_time + timedelta(milliseconds=offset_ms),
                monotonic_capture_time=100.1,
                camera_available=True,
                face_visible=True,
                eyes_closed=True,
                ear=0.12,
                quality=0.95,
                is_usable=True,
                frame_id="frame_B",
            )
        )

    eval_time = base_time + timedelta(milliseconds=3100)
    obs = window.evaluate(PilotId.PILOT_1, eval_time, config)

    # Must NOT be POSSIBLY_UNRESPONSIVE; only 100 ms separates distinct physical frames
    assert obs.observation_status != PilotObservationStatus.POSSIBLY_UNRESPONSIVE
    assert obs.observation_status == PilotObservationStatus.UNKNOWN
    # Effective evidence duration must reflect only the 100 ms distinct physical span
    assert obs.observation_duration_ms == 100


def test_duplicated_physical_frames_do_not_inflate_responsive_open_duration(
    base_time: datetime,
    config: VisionConfig,
) -> None:
    """
    Regression test for Issue 2 (responsive path):
    - At virtual 0 ms: frame A, open eyes (ear=0.32).
    - At virtual 100 ms: new frame B, open eyes (ear=0.32).
    - At virtual 1100 ms: reuse physical frame B with same frame ID and capture time.
    Only 100 ms separates distinct physical captures.
    min_open_window_ms is 1000 ms.
    Reused frame B must not inflate the span to 1100 ms to prematurely declare RESPONSIVE.
    """
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
            frame_id="frame_A",
        )
    )

    window.add_sample(
        PilotFrameEvidence(
            virtual_time=base_time + timedelta(milliseconds=100),
            monotonic_capture_time=100.1,
            camera_available=True,
            face_visible=True,
            eyes_closed=False,
            ear=0.32,
            quality=0.95,
            is_usable=True,
            frame_id="frame_B",
        )
    )

    window.add_sample(
        PilotFrameEvidence(
            virtual_time=base_time + timedelta(milliseconds=1100),
            monotonic_capture_time=100.1,
            camera_available=True,
            face_visible=True,
            eyes_closed=False,
            ear=0.32,
            quality=0.95,
            is_usable=True,
            frame_id="frame_B",
        )
    )

    eval_time = base_time + timedelta(milliseconds=1100)
    obs = window.evaluate(PilotId.PILOT_1, eval_time, config)

    # Must NOT be RESPONSIVE (needs >= 1000 ms distinct span); must be UNKNOWN with 100 ms
    assert obs.observation_status != PilotObservationStatus.RESPONSIVE
    assert obs.observation_status == PilotObservationStatus.UNKNOWN
    assert obs.observation_duration_ms == 100
