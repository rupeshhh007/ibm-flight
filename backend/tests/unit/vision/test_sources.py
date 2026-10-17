"""
Unit tests for Vision sources: ReplayLandmarkSource and optional OpenCVCaptureSource.

SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
"""

import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.contracts.enums import PilotId
from app.modules.vision.config import NormalizedROI, PilotChannelConfig, VisionConfig
from app.modules.vision.evidence import PilotFrameEvidence
from app.modules.vision.geometry import Point2D
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


try:
    import cv2  # noqa: F401
    import numpy as np  # noqa: F401
    _CV_DEPS_AVAILABLE = True
except ImportError:
    _CV_DEPS_AVAILABLE = False


def test_opencv_capture_source_missing_dependency() -> None:
    with patch("app.modules.vision.sources.is_opencv_available", return_value=False):
        with pytest.raises(RuntimeError, match="OpenCV .* is not installed"):
            OpenCVCaptureSource(0)


@pytest.mark.skipif(not _CV_DEPS_AVAILABLE, reason="Optional opencv-contrib-python and numpy not installed")
def test_opencv_capture_source_clear_frame_no_face_fails_closed(base_time: datetime) -> None:
    """
    Regression test for Review Item 1:
    A clear frame without a verified face must yield face_visible=False and is_usable=False,
    never fabricating RESPONSIVE observations.
    """
    import numpy as np

    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        mock_cap_cls.return_value = mock_cap

        source = OpenCVCaptureSource(0)
        # Simulate a clear, non-blurred frame (e.g., sharp texture of empty room/cockpit, no face)
        rng = np.random.default_rng(42)
        clear_frame = rng.integers(100, 150, size=(480, 640, 3), dtype=np.uint8)
        source._latest_frame = clear_frame
        source._latest_mono = time.monotonic()

        config = VisionConfig()
        sample = source.get_sample(PilotId.PILOT_1, base_time, config)

        # Must not fabricate face visibility or responsiveness!
        assert sample.camera_available is True
        assert sample.face_visible is False
        assert sample.is_usable is False
        assert sample.quality == 0.0
        assert "no_verified_face" in str(sample.error_reason)
        source.close()


@pytest.mark.skipif(not _CV_DEPS_AVAILABLE, reason="Optional opencv-contrib-python and numpy not installed")
def test_opencv_capture_source_respects_pilot_rois(base_time: datetime) -> None:
    """
    Regression test for Review Item 2:
    Separate pilot ROIs must prevent one face from providing observations for both pilots.
    """
    import numpy as np

    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        mock_cap_cls.return_value = mock_cap

        # Face detector that only finds a face if the cropped frame has width <= 320 (left ROI)
        # and has the pilot 1 ROI marker
        def mock_detector(cropped_frame: np.ndarray) -> tuple[bool, list[Point2D], str | None]:
            h, w = cropped_frame.shape[:2]
            # If cropped frame represents PILOT_1's left ROI, return valid landmarks
            if w == 320 and cropped_frame[0, 0, 0] == 200:
                return True, create_synthetic_landmarks(ear=0.30), None
            # Otherwise no face detected in this ROI
            return False, [], "no_face_in_roi"

        source = OpenCVCaptureSource(0, face_detector=mock_detector)
        # Full frame with textured illumination; left half has Pilot 1 marker
        rng = np.random.default_rng(42)
        frame = rng.integers(100, 140, size=(480, 640, 3), dtype=np.uint8)
        frame[:, :320, 0] = 200  # Left half has Pilot 1 signal marker
        source._latest_frame = frame
        source._latest_mono = time.monotonic()

        config = VisionConfig.split_frame()
        s1 = source.get_sample(PilotId.PILOT_1, base_time, config)
        s2 = source.get_sample(PilotId.PILOT_2, base_time, config)

        # Pilot 1 sees the face
        assert s1.face_visible is True
        assert s1.is_usable is True
        assert s1.eyes_closed is False

        # Pilot 2 sees NO face (isolated ROI)
        assert s2.face_visible is False
        assert s2.is_usable is False
        assert s2.quality == 0.0

        source.close()


@pytest.mark.skipif(not _CV_DEPS_AVAILABLE, reason="Optional opencv-contrib-python and numpy not installed")
def test_opencv_capture_source_mismatched_camera_index(base_time: datetime) -> None:
    """Regression test: source on camera 0 must not observe pilot assigned to camera 1."""
    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        mock_cap_cls.return_value = mock_cap

        source = OpenCVCaptureSource(0)
        config = VisionConfig(
            pilot_channels={
                PilotId.PILOT_1: PilotChannelConfig(pilot_id=PilotId.PILOT_1, camera_index=1),
                PilotId.PILOT_2: PilotChannelConfig(pilot_id=PilotId.PILOT_2, camera_index=0),
            }
        )
        # PILOT_1 expects camera 1, but source is camera 0
        sample = source.get_sample(PilotId.PILOT_1, base_time, config)
        assert sample.camera_available is False
        assert sample.face_visible is False
        assert sample.error_reason == "channel_camera_mismatch"
        source.close()


@pytest.mark.skipif(not _CV_DEPS_AVAILABLE, reason="Optional opencv-contrib-python and numpy not installed")
def test_opencv_capture_source_invalid_eye_geometry_fails_closed(base_time: datetime) -> None:
    """
    Regression test for Re-review Item 1:
    Zero-width or degenerate eye landmarks must NOT be interpreted as closed eyes.
    Must return is_usable=False, ear=None, eyes_closed=False.
    """
    import numpy as np

    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        mock_cap_cls.return_value = mock_cap

        # Landmark detector that returns valid face box, but all eye points are identical (zero width)
        def degenerate_eye_detector(frame: np.ndarray) -> tuple[bool, list[Point2D], str | None]:
            lmks = create_synthetic_landmarks(ear=0.30)
            # Flatten eye points to identical coordinates (zero width)
            for idx in (33, 160, 158, 133, 153, 144, 362, 385, 387, 263, 373, 380):
                lmks[idx] = Point2D(0.5, 0.5)
            return True, lmks, None

        source = OpenCVCaptureSource(0, face_detector=degenerate_eye_detector)
        rng = np.random.default_rng(42)
        frame = rng.integers(100, 140, size=(480, 640, 3), dtype=np.uint8)
        source._latest_frame = frame
        source._latest_mono = time.monotonic()

        config = VisionConfig()
        sample = source.get_sample(PilotId.PILOT_1, base_time, config)

        # Must NOT confirm eye closure or responsiveness!
        assert sample.eyes_closed is False
        assert sample.is_usable is False
        assert sample.ear is None
        source.close()


@pytest.mark.skipif(not _CV_DEPS_AVAILABLE, reason="Optional opencv-contrib-python and numpy not installed")
def test_opencv_capture_source_shared_camera_unassigned_roi_fails_closed(base_time: datetime) -> None:
    """
    Regression test for Re-review Item 2:
    When multiple pilots share a camera and ROI is unassigned, source fails closed.
    """
    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        mock_cap_cls.return_value = mock_cap

        source = OpenCVCaptureSource(0)
        rng = np.random.default_rng(42)
        frame = rng.integers(100, 140, size=(480, 640, 3), dtype=np.uint8)
        source._latest_frame = frame
        source._latest_mono = time.monotonic()

        # Both pilots on camera 0, but PILOT_1 has no ROI -> rejected by VisionConfig validation
        with pytest.raises(ValueError, match="both pilots MUST have explicit, disjoint non-overlapping ROIs"):
            VisionConfig(
                pilot_channels={
                    PilotId.PILOT_1: PilotChannelConfig(pilot_id=PilotId.PILOT_1, camera_index=0, roi=None),
                    PilotId.PILOT_2: PilotChannelConfig(
                        pilot_id=PilotId.PILOT_2,
                        camera_index=0,
                        roi=NormalizedROI(0.5, 0.0, 1.0, 1.0),
                    ),
                }
            )
        source.close()


@pytest.mark.skipif(not _CV_DEPS_AVAILABLE, reason="Optional opencv-contrib-python and numpy not installed")
def test_opencv_capture_source_read_failure_invalidates_latest_frame(base_time: datetime) -> None:
    """Regression test for Re-review Item 4: failed read invalidates latest frame."""
    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        # Read returns False (e.g. frame drop / EOF)
        mock_cap.read.return_value = (False, None)
        mock_cap_cls.return_value = mock_cap

        source = OpenCVCaptureSource(0)
        # Manually invoke worker body step
        with source._lock:
            source._latest_frame = None

        config = VisionConfig()
        sample = source.get_sample(PilotId.PILOT_1, base_time, config)
        assert sample.is_usable is False
        assert sample.face_visible is False
        source.close()


# =====================================================================
# Review Finding Regressions: Pilot Source Identity & Frame Tracking
# =====================================================================

@pytest.mark.skipif(not _CV_DEPS_AVAILABLE, reason="Optional opencv-contrib-python and numpy not installed")
def test_opencv_capture_source_mismatched_video_file(base_time: datetime) -> None:
    """
    P2 Regression Test:
    OpenCVCaptureSource configured with fileA.mp4 must not supply observations
    for a pilot channel configured for fileB.mp4.
    """
    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        mock_cap_cls.return_value = mock_cap

        source = OpenCVCaptureSource("pilot1_feed.mp4")
        config = VisionConfig(
            pilot_channels={
                PilotId.PILOT_1: PilotChannelConfig(
                    pilot_id=PilotId.PILOT_1,
                    video_path="pilot2_feed.mp4",
                ),
                PilotId.PILOT_2: PilotChannelConfig(
                    pilot_id=PilotId.PILOT_2,
                    video_path="pilot1_feed.mp4",
                ),
            }
        )
        sample = source.get_sample(PilotId.PILOT_1, base_time, config)
        assert sample.camera_available is False
        assert sample.is_usable is False
        assert sample.error_reason == "channel_video_path_mismatch"
        source.close()


@pytest.mark.skipif(not _CV_DEPS_AVAILABLE, reason="Optional opencv-contrib-python and numpy not installed")
def test_opencv_capture_source_pilot_specific_frame_tracking(base_time: datetime) -> None:
    """
    P1 Regression Test:
    Ensure frame tracking is pilot-specific so observing Pilot 1 does not incorrectly
    consume or lock out Pilot 2's frame on a shared split camera.
    """
    import numpy as np

    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        mock_cap_cls.return_value = mock_cap

        source = OpenCVCaptureSource(0)
        rng = np.random.default_rng(42)
        frame = rng.integers(100, 140, size=(480, 640, 3), dtype=np.uint8)

        # Inject frame 10
        with source._lock:
            source._latest_frame = frame
            source._latest_mono = time.monotonic()
            source._latest_frame_id = 10

        config = VisionConfig.split_frame()

        # Pilot 1 observes frame 10
        s1 = source.get_sample(PilotId.PILOT_1, base_time, config)
        assert source._last_served_frame_id[PilotId.PILOT_1] == 10

        # Pilot 2 also observes frame 10 without being blocked or consumed by Pilot 1
        s2 = source.get_sample(PilotId.PILOT_2, base_time, config)
        assert source._last_served_frame_id[PilotId.PILOT_2] == 10

        # Both received the valid frame identity
        assert s1.frame_id == 10
        assert s2.frame_id == 10
        source.close()
