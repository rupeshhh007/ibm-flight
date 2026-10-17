"""
Temporal evidence tracking and uncertainty-aware classification for pilot monitoring.

SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

from app.contracts.enums import PilotId, PilotObservationStatus
from app.contracts.models import PilotObservation
from .config import VisionConfig


@dataclass(frozen=True, slots=True)
class PilotFrameEvidence:
    """
    Evidence collected from a single frame/timestamp for one pilot.
    """
    virtual_time: datetime
    monotonic_capture_time: float
    camera_available: bool
    face_visible: bool
    eyes_closed: bool
    ear: float | None
    quality: float
    is_usable: bool
    error_reason: str | None = None


class PilotEvidenceWindow:
    """
    Maintains a bounded window of recent frame evidence for one pilot
    and applies conservative safety rules to produce canonical PilotObservation.
    """

    def __init__(self, max_samples: int = 120) -> None:
        self._max_samples = max_samples
        self._samples: deque[PilotFrameEvidence] = deque(maxlen=max_samples)

    def add_sample(self, sample: PilotFrameEvidence) -> None:
        self._samples.append(sample)

    def reset(self) -> None:
        self._samples.clear()

    @property
    def latest_sample(self) -> PilotFrameEvidence | None:
        return self._samples[-1] if self._samples else None

    def evaluate(
        self,
        pilot_id: PilotId,
        observed_at: datetime,
        config: VisionConfig,
    ) -> PilotObservation:
        # Guarantee timezone-aware UTC virtual timestamp
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        else:
            observed_at = observed_at.astimezone(timezone.utc)

        latest = self.latest_sample

        # 1. No evidence received at all
        if latest is None:
            return PilotObservation(
                pilot_id=pilot_id,
                observed_at=observed_at,
                observation_status=PilotObservationStatus.UNKNOWN,
                camera_available=False,
                face_visible=False,
                eyes_closed=False,
                observation_duration_ms=0,
                observation_quality=0.0,
            )

        # 2. Camera unavailable
        if not latest.camera_available:
            return PilotObservation(
                pilot_id=pilot_id,
                observed_at=observed_at,
                observation_status=PilotObservationStatus.UNKNOWN,
                camera_available=False,
                face_visible=False,
                eyes_closed=False,
                observation_duration_ms=0,
                observation_quality=0.0,
            )

        # 3. Face not visible / camera obstructed
        if not latest.face_visible:
            return PilotObservation(
                pilot_id=pilot_id,
                observed_at=observed_at,
                observation_status=PilotObservationStatus.UNKNOWN,
                camera_available=True,
                face_visible=False,
                eyes_closed=False,
                observation_duration_ms=0,
                observation_quality=0.0,
            )

        # 4. Error reason or sub-threshold usable quality
        if not latest.is_usable or latest.quality < config.min_usable_quality:
            return PilotObservation(
                pilot_id=pilot_id,
                observed_at=observed_at,
                observation_status=PilotObservationStatus.UNKNOWN,
                camera_available=True,
                face_visible=True,
                eyes_closed=False,
                observation_duration_ms=0,
                observation_quality=max(0.0, min(1.0, round(latest.quality, 2))),
            )

        # 5. Compute contiguous usable duration by scanning backwards
        contiguous_samples: list[PilotFrameEvidence] = []
        reversed_samples = list(reversed(self._samples))
        current_time = latest.virtual_time

        for s in reversed_samples:
            if not s.is_usable or s.quality < config.min_usable_quality:
                break
            gap_ms = (current_time - s.virtual_time).total_seconds() * 1000.0
            if gap_ms > config.max_gap_ms:
                break
            contiguous_samples.append(s)
            current_time = s.virtual_time

        # Calculate contiguous duration in milliseconds
        if len(contiguous_samples) <= 1:
            duration_ms = 0
        else:
            earliest_time = contiguous_samples[-1].virtual_time
            duration_ms = int((latest.virtual_time - earliest_time).total_seconds() * 1000.0)
            duration_ms = max(0, min(600_000, duration_ms))

        # Overall quality is the mean of contiguous usable samples
        mean_quality = sum(s.quality for s in contiguous_samples) / len(contiguous_samples)
        bounded_quality = max(0.0, min(1.0, round(mean_quality, 2)))

        # 6. Apply conservative classification rules
        # If duration is insufficient, abstain as UNKNOWN
        if duration_ms < config.min_observation_duration_ms:
            return PilotObservation(
                pilot_id=pilot_id,
                observed_at=observed_at,
                observation_status=PilotObservationStatus.UNKNOWN,
                camera_available=True,
                face_visible=True,
                eyes_closed=latest.eyes_closed,
                observation_duration_ms=duration_ms,
                observation_quality=bounded_quality,
            )

        # Evaluate window for sustained concerning closure
        if duration_ms >= config.min_closed_window_ms:
            cutoff = latest.virtual_time - timedelta(milliseconds=config.min_closed_window_ms)
            closed_window_samples = [s for s in contiguous_samples if s.virtual_time >= cutoff]
            if closed_window_samples:
                closed_count = sum(1 for s in closed_window_samples if s.eyes_closed)
                closed_ratio = closed_count / len(closed_window_samples)
                if closed_ratio >= config.min_valid_frame_ratio:
                    return PilotObservation(
                        pilot_id=pilot_id,
                        observed_at=observed_at,
                        observation_status=PilotObservationStatus.POSSIBLY_UNRESPONSIVE,
                        camera_available=True,
                        face_visible=True,
                        eyes_closed=True,
                        observation_duration_ms=duration_ms,
                        observation_quality=bounded_quality,
                    )

        # Evaluate window for positive responsiveness cues (sustained open eyes)
        if duration_ms >= config.min_open_window_ms:
            open_cutoff = latest.virtual_time - timedelta(milliseconds=config.min_open_window_ms)
            open_window_samples = [s for s in contiguous_samples if s.virtual_time >= open_cutoff]
            if open_window_samples:
                open_count = sum(1 for s in open_window_samples if not s.eyes_closed)
                open_ratio = open_count / len(open_window_samples)
                if open_ratio >= config.min_valid_frame_ratio:
                    return PilotObservation(
                        pilot_id=pilot_id,
                        observed_at=observed_at,
                        observation_status=PilotObservationStatus.RESPONSIVE,
                        camera_available=True,
                        face_visible=True,
                        eyes_closed=False,
                        observation_duration_ms=duration_ms,
                        observation_quality=bounded_quality,
                    )

        # Ambiguous / fluctuating cues -> safe UNKNOWN
        return PilotObservation(
            pilot_id=pilot_id,
            observed_at=observed_at,
            observation_status=PilotObservationStatus.UNKNOWN,
            camera_available=True,
            face_visible=True,
            eyes_closed=latest.eyes_closed,
            observation_duration_ms=duration_ms,
            observation_quality=bounded_quality,
        )
