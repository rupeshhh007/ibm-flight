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
    frame_id: int | str | None = None

    def __post_init__(self) -> None:
        # Guarantee timezone-aware UTC datetime
        if self.virtual_time.tzinfo is None or self.virtual_time.utcoffset() is None:
            object.__setattr__(self, "virtual_time", self.virtual_time.replace(tzinfo=timezone.utc))
        elif self.virtual_time.tzinfo != timezone.utc:
            object.__setattr__(self, "virtual_time", self.virtual_time.astimezone(timezone.utc))

        # Numeric validation on quality: must be finite and within [0.0, 1.0]
        if (
            not isinstance(self.quality, (int, float))
            or math.isnan(self.quality)
            or math.isinf(self.quality)
            or not (0.0 <= self.quality <= 1.0)
        ):
            object.__setattr__(self, "quality", 0.0)
            object.__setattr__(self, "is_usable", False)
            object.__setattr__(self, "error_reason", "invalid_numeric_quality")

        if self.ear is not None:
            if (
                not isinstance(self.ear, (int, float))
                or math.isnan(self.ear)
                or math.isinf(self.ear)
                or not (0.0 <= self.ear <= 1.0)
            ):
                object.__setattr__(self, "ear", None)
                object.__setattr__(self, "is_usable", False)
                object.__setattr__(self, "error_reason", "invalid_numeric_ear")

        # Independent fail-closed invariant: Eye geometry (ear) is mandatory for closed-eye evidence.
        # An observation cannot assert closed eyes if eye geometry is missing.
        if self.eyes_closed and self.ear is None:
            object.__setattr__(self, "is_usable", False)
            if not self.error_reason:
                object.__setattr__(self, "error_reason", "missing_eye_geometry")


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
        if sample.virtual_time.tzinfo is None or sample.virtual_time.utcoffset() is None:
            sample = replace(sample, virtual_time=sample.virtual_time.replace(tzinfo=timezone.utc))
        elif sample.virtual_time.tzinfo != timezone.utc:
            sample = replace(sample, virtual_time=sample.virtual_time.astimezone(timezone.utc))

        if self._samples:
            last = self._samples[-1]
            # Check for out-of-order timestamp: reset window to prevent corrupted/stale timeline
            if sample.virtual_time < last.virtual_time:
                logger.warning(
                    "Rejecting out-of-order sample: %s is earlier than last %s; resetting window",
                    sample.virtual_time,
                    last.virtual_time,
                )
                self.reset()
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
                observation_quality=max(0.0, min(1.0, float(q))),
            )

        # 6. Compute general contiguous usable duration and quality
        contiguous_samples: list[PilotFrameEvidence] = []
        curr_t = latest.virtual_time
        for s in reversed(eligible):
            if not s.is_usable or s.quality < config.min_usable_quality:
                break
            gap_ms = (curr_t - s.virtual_time).total_seconds() * 1000.0
            if s is not latest and (gap_ms <= 0.0 or gap_ms > config.max_gap_ms):
                break
            contiguous_samples.append(s)
            curr_t = s.virtual_time

        # Filter contiguous samples to distinct physical frames to prevent repeated frames
        # from inflating evidence duration.
        distinct_contiguous: list[PilotFrameEvidence] = []
        seen_contiguous_frames: set[object] = set()
        for s in contiguous_samples:
            frame_key = s.frame_id if s.frame_id is not None else s.monotonic_capture_time
            if frame_key not in seen_contiguous_frames:
                seen_contiguous_frames.add(frame_key)
                distinct_contiguous.append(s)

        if len(distinct_contiguous) < 2:
            duration_ms = 0
        else:
            duration_ms = int((distinct_contiguous[0].virtual_time - distinct_contiguous[-1].virtual_time).total_seconds() * 1000.0)
            duration_ms = max(0, min(600_000, duration_ms))

        mean_q = sum(s.quality for s in contiguous_samples) / max(1, len(contiguous_samples))
        # Exact bounded float precision: do not round upward before Guardian threshold evaluation
        bounded_q = max(0.0, min(1.0, float(mean_q)))

        # 7. Independent sustained temporal evidence evaluation
        # Disambiguate latest sample: must satisfy strict thresholds.
        # Fail closed: eye geometry (ear) is strictly required for closed-eye classification.
        is_latest_closed = latest.eyes_closed and (latest.ear is not None and latest.ear < config.eye_closed_ear_threshold)
        is_latest_open = (not latest.eyes_closed) and (latest.ear is not None and latest.ear >= config.eye_open_ear_threshold)

        # Evaluate sustained closed-eye window for POSSIBLY_UNRESPONSIVE
        if is_latest_closed:
            closed_run: list[PilotFrameEvidence] = []
            curr_t = latest.virtual_time
            for s in reversed(eligible):
                if not s.is_usable or s.quality < config.min_usable_quality:
                    break
                gap_ms = (curr_t - s.virtual_time).total_seconds() * 1000.0
                if s is not latest and (gap_ms <= 0.0 or gap_ms > config.max_gap_ms):
                    break
                # Fail-closed: missing eye geometry (ear is None), ambiguous ear, or open eyes immediately breaks run
                if not s.eyes_closed or s.ear is None or s.ear >= config.eye_closed_ear_threshold:
                    break
                closed_run.append(s)
                curr_t = s.virtual_time

            # Enforce physical frame independence: filter to distinct physical frames
            distinct_closed: list[PilotFrameEvidence] = []
            seen_closed_frames: set[object] = set()
            for s in closed_run:
                frame_key = s.frame_id if s.frame_id is not None else s.monotonic_capture_time
                if frame_key not in seen_closed_frames:
                    seen_closed_frames.add(frame_key)
                    distinct_closed.append(s)

            if len(distinct_closed) >= 2:
                # Span between latest distinct physical frame and earliest distinct physical frame
                closed_span_ms = int((distinct_closed[0].virtual_time - distinct_closed[-1].virtual_time).total_seconds() * 1000.0)
                if (
                    closed_span_ms >= config.min_closed_window_ms
                    and closed_span_ms >= config.min_observation_duration_ms
                ):
                    closed_count = sum(
                        1 for s in closed_run
                        if s.eyes_closed and s.ear is not None and s.ear < config.eye_closed_ear_threshold
                    )
                    closed_ratio = closed_count / len(closed_run)
                    if closed_ratio >= config.min_valid_frame_ratio:
                        mean_closed_q = sum(s.quality for s in closed_run) / len(closed_run)
                        return PilotObservation(
                            pilot_id=pilot_id,
                            observed_at=observed_at,
                            observation_status=PilotObservationStatus.POSSIBLY_UNRESPONSIVE,
                            camera_available=True,
                            face_visible=True,
                            eyes_closed=True,
                            observation_duration_ms=closed_span_ms,
                            observation_quality=max(0.0, min(1.0, float(mean_closed_q))),
                        )

        # Evaluate sustained open-eye window for RESPONSIVE
        if is_latest_open:
            open_run: list[PilotFrameEvidence] = []
            curr_t = latest.virtual_time
            for s in reversed(eligible):
                if not s.is_usable or s.quality < config.min_usable_quality:
                    break
                gap_ms = (curr_t - s.virtual_time).total_seconds() * 1000.0
                if s is not latest and (gap_ms <= 0.0 or gap_ms > config.max_gap_ms):
                    break
                # Broken by confirmed closed sample or ambiguous sample (ear < eye_open_ear_threshold)
                if s.eyes_closed or s.ear is None or s.ear < config.eye_open_ear_threshold:
                    break
                open_run.append(s)
                curr_t = s.virtual_time

            # Enforce physical frame independence: filter to distinct physical frames
            distinct_open: list[PilotFrameEvidence] = []
            seen_open_frames: set[object] = set()
            for s in open_run:
                frame_key = s.frame_id if s.frame_id is not None else s.monotonic_capture_time
                if frame_key not in seen_open_frames:
                    seen_open_frames.add(frame_key)
                    distinct_open.append(s)

            if len(distinct_open) >= 2:
                # Span between latest distinct physical frame and earliest distinct physical frame
                open_span_ms = int((distinct_open[0].virtual_time - distinct_open[-1].virtual_time).total_seconds() * 1000.0)
                if (
                    open_span_ms >= config.min_open_window_ms
                    and open_span_ms >= config.min_observation_duration_ms
                ):
                    open_count = sum(
                        1 for s in open_run
                        if not s.eyes_closed and s.ear is not None and s.ear >= config.eye_open_ear_threshold
                    )
                    open_ratio = open_count / len(open_run)
                    if open_ratio >= config.min_valid_frame_ratio:
                        mean_open_q = sum(s.quality for s in open_run) / len(open_run)
                        return PilotObservation(
                            pilot_id=pilot_id,
                            observed_at=observed_at,
                            observation_status=PilotObservationStatus.RESPONSIVE,
                            camera_available=True,
                            face_visible=True,
                            eyes_closed=False,
                            observation_duration_ms=open_span_ms,
                            observation_quality=max(0.0, min(1.0, float(mean_open_q))),
                        )

        # Ambiguous, sub-duration, or fluctuating cues -> safe UNKNOWN
        # Fail-closed: eyes_closed cannot be asserted without valid eye geometry (ear is not None)
        safe_eyes_closed = latest.eyes_closed if latest.ear is not None else False
        return PilotObservation(
            pilot_id=pilot_id,
            observed_at=observed_at,
            observation_status=PilotObservationStatus.UNKNOWN,
            camera_available=True,
            face_visible=True,
            eyes_closed=safe_eyes_closed,
            observation_duration_ms=duration_ms,
            observation_quality=bounded_q,
        )
