"""
Temporal evidence tracking and uncertainty-aware classification for pilot monitoring.

SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Sequence

from app.contracts.enums import PilotId, PilotObservationStatus
from app.contracts.models import PilotObservation
from .config import VisionConfig

logger = logging.getLogger(__name__)


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

    def __post_init__(self) -> None:
        # Guarantee timezone-aware UTC datetime
        if self.virtual_time.tzinfo is None or self.virtual_time.utcoffset() is None:
            raise ValueError("PilotFrameEvidence virtual_time must be timezone-aware UTC")

        # Numeric validation on quality and ear
        if not isinstance(self.quality, (int, float)) or math.isnan(self.quality) or math.isinf(self.quality):
            object.__setattr__(self, "quality", 0.0)
            object.__setattr__(self, "is_usable", False)
            object.__setattr__(self, "error_reason", "invalid_numeric_quality")

        if self.ear is not None:
            if not isinstance(self.ear, (int, float)) or math.isnan(self.ear) or math.isinf(self.ear):
                object.__setattr__(self, "ear", None)
                object.__setattr__(self, "is_usable", False)
                object.__setattr__(self, "error_reason", "invalid_numeric_ear")


class PilotEvidenceWindow:
    """
    Maintains a bounded window of recent frame evidence for one pilot
    and applies conservative safety rules to produce canonical PilotObservation.
    """

    def __init__(self, max_samples: int = 120) -> None:
        self._max_samples = max_samples
        self._samples: deque[PilotFrameEvidence] = deque(maxlen=max_samples)

    def add_sample(self, sample: PilotFrameEvidence) -> None:
        # Normalize sample virtual_time to UTC
        if sample.virtual_time.tzinfo != timezone.utc:
            sample = replace(sample, virtual_time=sample.virtual_time.astimezone(timezone.utc))

        if self._samples:
            last = self._samples[-1]
            # Check for out-of-order timestamp: reject to prevent corrupting monotonic timeline
            if sample.virtual_time < last.virtual_time:
                logger.warning(
                    "Rejecting out-of-order sample: %s is earlier than last %s",
                    sample.virtual_time,
                    last.virtual_time,
                )
                return

            # Check for repeated / duplicate timestamp: update in place without inflating sample count
            if sample.virtual_time == last.virtual_time:
                self._samples[-1] = sample
                return

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

        # 1. Filter samples: reject future samples relative to requested observed_at
        eligible = [s for s in self._samples if s.virtual_time <= observed_at]

        if not eligible:
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

        latest = eligible[-1]

        # 2. Check evidence staleness against requested virtual timestamp
        staleness_ms = (observed_at - latest.virtual_time).total_seconds() * 1000.0
        if staleness_ms > config.max_gap_ms:
            # Stale evidence: gap exceeded between latest frame and requested evaluation time
            return PilotObservation(
                pilot_id=pilot_id,
                observed_at=observed_at,
                observation_status=PilotObservationStatus.UNKNOWN,
                camera_available=latest.camera_available,
                face_visible=latest.face_visible,
                eyes_closed=False,
                observation_duration_ms=0,
                observation_quality=0.0,
            )

        # 3. Camera unavailable
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

        # 4. Face not visible / camera obstructed
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

        # 5. Error reason or sub-threshold usable quality
        if not latest.is_usable or latest.quality < config.min_usable_quality:
            q = latest.quality if not (math.isnan(latest.quality) or math.isinf(latest.quality)) else 0.0
            return PilotObservation(
                pilot_id=pilot_id,
                observed_at=observed_at,
                observation_status=PilotObservationStatus.UNKNOWN,
                camera_available=True,
                face_visible=True,
                eyes_closed=False,
                observation_duration_ms=0,
                observation_quality=max(0.0, min(1.0, round(q, 2))),
            )

        # 6. Compute contiguous usable duration by scanning backwards
        contiguous_samples: list[PilotFrameEvidence] = []
        current_time = latest.virtual_time

        for s in reversed(eligible):
            if not s.is_usable or s.quality < config.min_usable_quality:
                break
            gap_ms = (current_time - s.virtual_time).total_seconds() * 1000.0
            if s is not latest:
                # Monotonicity check: gap must be strictly positive and bounded
                if gap_ms <= 0.0 or gap_ms > config.max_gap_ms:
                    break
            contiguous_samples.append(s)
            current_time = s.virtual_time

        # Calculate contiguous duration in milliseconds across distinct timestamps
        if len(contiguous_samples) < 2:
            duration_ms = 0
        else:
            earliest_time = contiguous_samples[-1].virtual_time
            duration_ms = int((latest.virtual_time - earliest_time).total_seconds() * 1000.0)
            duration_ms = max(0, min(600_000, duration_ms))

        # Overall quality is the mean of contiguous usable samples
        mean_quality = sum(s.quality for s in contiguous_samples) / max(1, len(contiguous_samples))
        if math.isnan(mean_quality) or math.isinf(mean_quality):
            bounded_quality = 0.0
        else:
            bounded_quality = max(0.0, min(1.0, round(mean_quality, 2)))

        # 7. Apply conservative classification rules
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
        # Requires at least 2 distinct temporal samples and duration >= min_closed_window_ms
        if duration_ms >= config.min_closed_window_ms and len(contiguous_samples) >= 2:
            cutoff = latest.virtual_time - timedelta(milliseconds=config.min_closed_window_ms)
            closed_window_samples = [s for s in contiguous_samples if s.virtual_time >= cutoff]
            if len(closed_window_samples) >= 2:
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
        if duration_ms >= config.min_open_window_ms and len(contiguous_samples) >= 2:
            open_cutoff = latest.virtual_time - timedelta(milliseconds=config.min_open_window_ms)
            open_window_samples = [s for s in contiguous_samples if s.virtual_time >= open_cutoff]
            if len(open_window_samples) >= 2:
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
