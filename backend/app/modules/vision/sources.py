"""
Frame and landmark sources for AeroGuard Vision subsystem.
Includes deterministic replay sources and lazy optional OpenCV/MediaPipe providers.

SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence, runtime_checkable

from app.contracts.enums import PilotId
from .config import VisionConfig, canonical_source_key
from .evidence import PilotFrameEvidence
from .geometry import (
    LEFT_EYE_INDICES,
    RIGHT_EYE_INDICES,
    NormalizedROI,
    Point2D,
    evaluate_landmark_quality,
    extract_ear_from_landmarks,
)

logger = logging.getLogger(__name__)


def is_opencv_available() -> bool:
    try:
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


def is_mediapipe_available() -> bool:
    try:
        import mediapipe  # noqa: F401
        return True
    except ImportError:
        return False


@runtime_checkable
class FrameSource(Protocol):
    """Protocol for frame/landmark suppliers."""

    def configure_scenario(self, scenario_id: str) -> None: ...
    def get_sample(self, pilot_id: PilotId, virtual_time: datetime, config: VisionConfig) -> PilotFrameEvidence: ...
    def close(self) -> None: ...


def create_synthetic_landmarks(
    ear: float,
    center_x: float = 0.5,
    center_y: float = 0.5,
    scale: float = 0.2,
) -> list[Point2D]:
    """
    Generate synthetic 468-point landmarks with controlled EAR for testing.
    Places landmarks inside [0.0, 1.0].
    """
    landmarks = [Point2D(center_x, center_y) for _ in range(468)]
    # Place left eye points around (center_x - scale * 0.3, center_y)
    lx = center_x - scale * 0.3
    ly = center_y
    h_dist = scale * 0.2
    v_dist = h_dist * ear

    landmarks[33] = Point2D(lx - h_dist / 2, ly)
    landmarks[133] = Point2D(lx + h_dist / 2, ly)
    landmarks[160] = Point2D(lx - h_dist / 4, ly - v_dist / 2)
    landmarks[158] = Point2D(lx + h_dist / 4, ly - v_dist / 2)
    landmarks[144] = Point2D(lx - h_dist / 4, ly + v_dist / 2)
    landmarks[153] = Point2D(lx + h_dist / 4, ly + v_dist / 2)

    # Place right eye points around (center_x + scale * 0.3, center_y)
    rx = center_x + scale * 0.3
    ry = center_y
    landmarks[263] = Point2D(rx + h_dist / 2, ry)
    landmarks[362] = Point2D(rx - h_dist / 2, ry)
    landmarks[385] = Point2D(rx - h_dist / 4, ry - v_dist / 2)
    landmarks[387] = Point2D(rx + h_dist / 4, ry - v_dist / 2)
    landmarks[380] = Point2D(rx - h_dist / 4, ry + v_dist / 2)
    landmarks[373] = Point2D(rx + h_dist / 4, ry + v_dist / 2)

    # Place face boundary points (forehead, chin, cheeks) for realistic bbox
    landmarks[10] = Point2D(center_x, max(0.01, center_y - scale * 0.6))
    landmarks[152] = Point2D(center_x, min(0.99, center_y + scale * 0.6))
    landmarks[234] = Point2D(max(0.01, center_x - scale * 0.6), center_y)
    landmarks[454] = Point2D(min(0.99, center_x + scale * 0.6), center_y)

    return landmarks


class ReplayLandmarkSource:
    """
    Deterministic replay provider delivering controlled synthetic landmark observations.
    Primary demo and test engine. Requires zero external CV packages.
    """

    def __init__(self) -> None:
        self._scenario_id: str = "normal_flight"
        self._frame_seq: int = 0
        self._custom_tracks: dict[PilotId, list[PilotFrameEvidence]] = {
            PilotId.PILOT_1: [],
            PilotId.PILOT_2: [],
        }
        self._custom_track_indices: dict[PilotId, int] = {
            PilotId.PILOT_1: 0,
            PilotId.PILOT_2: 0,
        }
        self._custom_generators: dict[PilotId, Callable[[PilotId, datetime, VisionConfig], PilotFrameEvidence] | None] = {
            PilotId.PILOT_1: None,
            PilotId.PILOT_2: None,
        }
        self._closed: bool = False

    def configure_scenario(self, scenario_id: str) -> None:
        self._scenario_id = scenario_id
        self._custom_track_indices[PilotId.PILOT_1] = 0
        self._custom_track_indices[PilotId.PILOT_2] = 0

    def set_pilot_track(self, pilot_id: PilotId, track: list[PilotFrameEvidence]) -> None:
        self._custom_tracks[pilot_id] = list(track)
        self._custom_track_indices[pilot_id] = 0

    def set_pilot_generator(
        self,
        pilot_id: PilotId,
        generator: Callable[[PilotId, datetime, VisionConfig], PilotFrameEvidence] | None,
    ) -> None:
        self._custom_generators[pilot_id] = generator

    def get_sample(
        self,
        pilot_id: PilotId,
        virtual_time: datetime,
        config: VisionConfig,
    ) -> PilotFrameEvidence:
        # Strict timestamp validation: reject naive timestamps per contract
        if virtual_time.tzinfo is None or virtual_time.utcoffset() is None:
            raise ValueError("virtual_time datetime must be timezone-aware")
        virtual_time = virtual_time.astimezone(timezone.utc)

        now_mono = time.monotonic()
        self._frame_seq += 1
        frame_id = f"replay_{pilot_id.value}_{self._frame_seq}"

        if self._closed:
            return PilotFrameEvidence(
                virtual_time=virtual_time,
                monotonic_capture_time=now_mono,
                camera_available=False,
                face_visible=False,
                eyes_closed=False,
                ear=None,
                quality=0.0,
                is_usable=False,
                error_reason="source_closed",
                frame_id=frame_id,
            )

        # Invariant: Channel must be explicitly configured and enabled
        channel = config.pilot_channels.get(pilot_id)
        if channel is None or not channel.enabled:
            return PilotFrameEvidence(
                virtual_time=virtual_time,
                monotonic_capture_time=now_mono,
                camera_available=False,
                face_visible=False,
                eyes_closed=False,
                ear=None,
                quality=0.0,
                is_usable=False,
                error_reason="channel_disabled_or_unassigned",
                frame_id=frame_id,
            )

        # Check for injected custom generator
        if gen := self._custom_generators.get(pilot_id):
            return gen(pilot_id, virtual_time, config)

        # Check for injected step sequence track
        track = self._custom_tracks.get(pilot_id, [])
        idx = self._custom_track_indices.get(pilot_id, 0)
        if track and idx < len(track):
            sample = track[idx]
            self._custom_track_indices[pilot_id] = idx + 1
            return sample

        # Default replay track matching stable scenarios
        if self._scenario_id == "camera_obstructed":
            return PilotFrameEvidence(
                virtual_time=virtual_time,
                monotonic_capture_time=now_mono,
                camera_available=False,
                face_visible=False,
                eyes_closed=False,
                ear=None,
                quality=0.0,
                is_usable=False,
                error_reason="camera_obstructed",
                frame_id=frame_id,
            )

        if self._scenario_id in {"dual_pilot_atc_connected", "dual_pilot_atc_disconnected"}:
            # Sustained closed eyes for both pilots
            ear = 0.12
            return PilotFrameEvidence(
                virtual_time=virtual_time,
                monotonic_capture_time=now_mono,
                camera_available=True,
                face_visible=True,
                eyes_closed=True,
                ear=ear,
                quality=0.92,
                is_usable=True,
                error_reason=None,
                frame_id=frame_id,
            )

        if self._scenario_id == "single_pilot_unresponsive":
            if pilot_id == PilotId.PILOT_1:
                # Sustained closed eyes for Pilot 1
                return PilotFrameEvidence(
                    virtual_time=virtual_time,
                    monotonic_capture_time=now_mono,
                    camera_available=True,
                    face_visible=True,
                    eyes_closed=True,
                    ear=0.12,
                    quality=0.92,
                    is_usable=True,
                    error_reason=None,
                    frame_id=frame_id,
                )
            else:
                # Responsive open eyes for Pilot 2
                return PilotFrameEvidence(
                    virtual_time=virtual_time,
                    monotonic_capture_time=now_mono,
                    camera_available=True,
                    face_visible=True,
                    eyes_closed=False,
                    ear=0.32,
                    quality=0.95,
                    is_usable=True,
                    error_reason=None,
                    frame_id=frame_id,
                )

        # normal_flight default
        return PilotFrameEvidence(
            virtual_time=virtual_time,
            monotonic_capture_time=now_mono,
            camera_available=True,
            face_visible=True,
            eyes_closed=False,
            ear=0.32,
            quality=0.95,
            is_usable=True,
            error_reason=None,
            frame_id=frame_id,
        )

    def close(self) -> None:
        self._closed = True


class OpenCVCaptureSource:
    """
    Optional live webcam or local video file capture source using OpenCV.
    Lazily imports cv2. If OpenCV is not installed, raises an informative error at construction time.
    Enforces per-pilot ROI cropping and requires verified face detection.
    """

    def __init__(
        self,
        camera_index_or_path: int | str | Path = 0,
        target_fps: int = 15,
        face_detector: Callable[[Any], tuple[bool, list[Point2D], str | None]] | None = None,
    ) -> None:
        if not is_opencv_available():
            raise RuntimeError(
                "OpenCV (cv2) is not installed. To use real camera/video input, install optional "
                "packages (e.g. pip install opencv-contrib-python mediapipe). Deterministic replay mode "
                "is available without any extra packages."
            )
        import cv2  # type: ignore

        self._cv2 = cv2
        self._target = camera_index_or_path
        self._face_detector = face_detector
        self._cap = cv2.VideoCapture(camera_index_or_path)
        if not self._cap.isOpened():
            logger.warning("Failed to open OpenCV capture source: %s", camera_index_or_path)

        self._target_fps = target_fps
        self._lock = threading.Lock()
        self._latest_frame = None
        self._latest_mono: float = 0.0
        self._frame_seq: int = 0
        self._latest_frame_id: int | None = None
        self._last_served_frame_id: dict[PilotId, int | None] = {}
        self._last_served_mono: dict[PilotId, float] = {}
        self._running: bool = True
        self._thread = threading.Thread(target=self._capture_worker, daemon=True)
        self._thread.start()

    def set_face_detector(
        self,
        detector: Callable[[Any], tuple[bool, list[Point2D], str | None]] | None,
    ) -> None:
        self._face_detector = detector

    def _capture_step(self) -> None:
        """
        Execute a single capture attempt from the underlying device.
        On any read failure (e.g. read() returning False/None, malformed frame, or exception),
        the cached frame is immediately invalidated so stale/cached evidence is never reused.
        """
        if self._cap is None:
            with self._lock:
                self._latest_frame = None
                self._latest_mono = 0.0
                self._latest_frame_id = None
            return

        try:
            if not self._cap.isOpened():
                with self._lock:
                    self._latest_frame = None
                    self._latest_mono = 0.0
                    self._latest_frame_id = None
                return

            res = self._cap.read()
            if isinstance(res, tuple) and len(res) == 2:
                ret, frame = res
                if ret and frame is not None and getattr(frame, "size", 0) > 0 and getattr(frame, "ndim", 0) >= 2:
                    with self._lock:
                        self._frame_seq += 1
                        self._latest_frame = frame
                        self._latest_mono = time.monotonic()
                        self._latest_frame_id = self._frame_seq
                    return

            # Failed read, EOF, or malformed frame: immediately invalidate cached frame
            with self._lock:
                self._latest_frame = None
                self._latest_mono = 0.0
                self._latest_frame_id = None
        except Exception:
            with self._lock:
                self._latest_frame = None
                self._latest_mono = 0.0
                self._latest_frame_id = None

    def _capture_worker(self) -> None:
        delay = 1.0 / max(1, self._target_fps)
        while self._running:
            self._capture_step()
            time.sleep(delay)

    def configure_scenario(self, scenario_id: str) -> None:
        # Live video capture does not change hardware input on scenario reset
        pass

    def canonical_source_key(self) -> tuple[str, int | str]:
        """Return the canonical source identity for this capture source."""
        if isinstance(self._target, (str, Path)):
            return canonical_source_key(video_path=self._target)
        return canonical_source_key(camera_index=self._target)

    def get_sample(
        self,
        pilot_id: PilotId,
        virtual_time: datetime,
        config: VisionConfig,
    ) -> PilotFrameEvidence:
        # Strict timestamp validation: reject naive timestamps per contract
        if virtual_time.tzinfo is None or virtual_time.utcoffset() is None:
            raise ValueError("virtual_time datetime must be timezone-aware")
        virtual_time = virtual_time.astimezone(timezone.utc)

        now_mono = time.monotonic()

        # Invariant: Channel must be explicitly configured and enabled
        channel = config.pilot_channels.get(pilot_id)
        if channel is None or not channel.enabled:
            return PilotFrameEvidence(
                virtual_time=virtual_time,
                monotonic_capture_time=now_mono,
                camera_available=False,
                face_visible=False,
                eyes_closed=False,
                ear=None,
                quality=0.0,
                is_usable=False,
                error_reason="channel_disabled_or_unassigned",
            )

        # Strict source identity validation: verify channel configuration matches this source
        if channel.canonical_source_key() != self.canonical_source_key():
            expected_type, _ = channel.canonical_source_key()
            error_reason = "channel_video_path_mismatch" if expected_type == "video" else "channel_camera_mismatch"
            return PilotFrameEvidence(
                virtual_time=virtual_time,
                monotonic_capture_time=now_mono,
                camera_available=False,
                face_visible=False,
                eyes_closed=False,
                ear=None,
                quality=0.0,
                is_usable=False,
                error_reason=error_reason,
            )

        if not self._cap or not self._cap.isOpened():
            return PilotFrameEvidence(
                virtual_time=virtual_time,
                monotonic_capture_time=now_mono,
                camera_available=False,
                face_visible=False,
                eyes_closed=False,
                ear=None,
                quality=0.0,
                is_usable=False,
                error_reason="camera_device_unavailable",
            )

        with self._lock:
            frame = self._latest_frame
            frame_mono = self._latest_mono
            frame_id = self._latest_frame_id

        # Pilot-specific tracking: record that this frame was served to pilot_id
        # (Pilot 1 observing this frame does not consume Pilot 2's frame)
        self._last_served_frame_id[pilot_id] = frame_id
        self._last_served_mono[pilot_id] = frame_mono

        if frame is None:
            return PilotFrameEvidence(
                virtual_time=virtual_time,
                monotonic_capture_time=now_mono,
                camera_available=True,
                face_visible=False,
                eyes_closed=False,
                ear=None,
                quality=0.0,
                is_usable=False,
                error_reason="no_frame_captured_yet",
                frame_id=frame_id,
            )

        # Check frame staleness against max_frame_age_ms
        age_ms = (now_mono - frame_mono) * 1000.0
        if age_ms > config.max_frame_age_ms:
            return PilotFrameEvidence(
                virtual_time=virtual_time,
                monotonic_capture_time=frame_mono,
                camera_available=True,
                face_visible=False,
                eyes_closed=False,
                ear=None,
                quality=0.0,
                is_usable=False,
                error_reason="stale_frame",
                frame_id=frame_id,
            )

        # Isolate pilot ROI: crop frame to the assigned sub-region
        if channel.roi is not None:
            h, w = frame.shape[:2]
            x1 = max(0, int(channel.roi.x_min * w))
            y1 = max(0, int(channel.roi.y_min * h))
            x2 = min(w, int(channel.roi.x_max * w))
            y2 = min(h, int(channel.roi.y_max * h))
            if x2 <= x1 or y2 <= y1:
                return PilotFrameEvidence(
                    virtual_time=virtual_time,
                    monotonic_capture_time=frame_mono,
                    camera_available=True,
                    face_visible=False,
                    eyes_closed=False,
                    ear=None,
                    quality=0.0,
                    is_usable=False,
                    error_reason="invalid_or_empty_roi",
                    frame_id=frame_id,
                )
            pilot_frame = frame[y1:y2, x1:x2]
        else:
            # Enforce pilot isolation: if multiple pilots share this camera source,
            # unassigned ROI is forbidden to prevent cross-pilot observation contamination.
            other_pilots_on_source = [
                ch for pid, ch in config.pilot_channels.items()
                if pid != pilot_id and ch.enabled and (
                    ch.camera_index == self._target or
                    (ch.camera_index is None and (self._target == 0 or isinstance(self._target, str)))
                )
            ]
            if other_pilots_on_source:
                return PilotFrameEvidence(
                    virtual_time=virtual_time,
                    monotonic_capture_time=frame_mono,
                    camera_available=True,
                    face_visible=False,
                    eyes_closed=False,
                    ear=None,
                    quality=0.0,
                    is_usable=False,
                    error_reason="unassigned_roi_on_shared_camera",
                    frame_id=frame_id,
                )
            pilot_frame = frame

        # Basic image quality: blur (Laplacian variance) and illumination (mean brightness)
        gray = self._cv2.cvtColor(pilot_frame, self._cv2.COLOR_BGR2GRAY)
        mean_brightness = float(self._cv2.mean(gray)[0])
        laplacian_var = float(self._cv2.Laplacian(gray, self._cv2.CV_64F).var())

        # Check illumination bounds
        if mean_brightness < 20.0 or mean_brightness > 240.0:
            return PilotFrameEvidence(
                virtual_time=virtual_time,
                monotonic_capture_time=frame_mono,
                camera_available=True,
                face_visible=False,
                eyes_closed=False,
                ear=None,
                quality=0.0,
                is_usable=False,
                error_reason="poor_illumination",
                frame_id=frame_id,
            )

        # Check blur
        if laplacian_var < 30.0:
            return PilotFrameEvidence(
                virtual_time=virtual_time,
                monotonic_capture_time=frame_mono,
                camera_available=True,
                face_visible=False,
                eyes_closed=False,
                ear=None,
                quality=0.0,
                is_usable=False,
                error_reason="severe_blur",
                frame_id=frame_id,
            )

        # Invariant 1: Verified face detection is mandatory.
        # Clear frames with no face must NEVER produce face_visible=True or RESPONSIVE observations.
        if self._face_detector is not None:
            detected, landmarks, err = self._face_detector(pilot_frame)
            if not detected or not landmarks:
                return PilotFrameEvidence(
                    virtual_time=virtual_time,
                    monotonic_capture_time=frame_mono,
                    camera_available=True,
                    face_visible=False,
                    eyes_closed=False,
                    ear=None,
                    quality=0.0,
                    is_usable=False,
                    error_reason=err or "no_face_detected_in_roi",
                    frame_id=frame_id,
                )

            # Evaluate landmark quality
            usable, lmk_quality = evaluate_landmark_quality(landmarks)
            if not usable or lmk_quality < config.min_usable_quality:
                return PilotFrameEvidence(
                    virtual_time=virtual_time,
                    monotonic_capture_time=frame_mono,
                    camera_available=True,
                    face_visible=True,
                    eyes_closed=False,
                    ear=None,
                    quality=lmk_quality,
                    is_usable=False,
                    error_reason="sub_threshold_landmark_quality",
                    frame_id=frame_id,
                )

            left_ear, right_ear, avg_ear = extract_ear_from_landmarks(landmarks)
            if avg_ear is None or not (0.0 <= avg_ear <= 1.0):
                return PilotFrameEvidence(
                    virtual_time=virtual_time,
                    monotonic_capture_time=frame_mono,
                    camera_available=True,
                    face_visible=True,
                    eyes_closed=False,
                    ear=None,
                    quality=0.0,
                    is_usable=False,
                    error_reason="invalid_or_incomplete_eye_geometry",
                    frame_id=frame_id,
                )

            eyes_closed = avg_ear < config.eye_closed_ear_threshold

            return PilotFrameEvidence(
                virtual_time=virtual_time,
                monotonic_capture_time=frame_mono,
                camera_available=True,
                face_visible=True,
                eyes_closed=eyes_closed,
                ear=avg_ear,
                quality=lmk_quality,
                is_usable=True,
                error_reason=None,
                frame_id=frame_id,
            )
        else:
            # Without verified face detection running on the frame, fail-closed as UNKNOWN
            return PilotFrameEvidence(
                virtual_time=virtual_time,
                monotonic_capture_time=frame_mono,
                camera_available=True,
                face_visible=False,
                eyes_closed=False,
                ear=None,
                quality=0.0,
                is_usable=False,
                error_reason="no_verified_face_detection_available",
                frame_id=frame_id,
            )

    def close(self) -> None:
        self._running = False
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
