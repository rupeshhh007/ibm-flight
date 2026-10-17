"""
Private typed configuration for the Vision subsystem.

SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.contracts.enums import PilotId
from .geometry import NormalizedROI


@dataclass(frozen=True, slots=True)
class PilotChannelConfig:
    """
    Mapping for one pilot to a physical or virtual input.
    - If camera_index or video_path is provided, specifies the capture source.
    - If roi is provided, frames from the source are cropped to this normalized region.
    - If enabled is False, the pilot is considered unmonitored / unavailable (yields UNKNOWN).
    """
    pilot_id: PilotId
    roi: NormalizedROI | None = None
    camera_index: int | None = None
    video_path: Path | str | None = None
    enabled: bool = True


@dataclass
class VisionConfig:
    """
    Internal thresholds and operational configuration for evidence evaluation.
    None of these fields are exposed on public contracts.
    """
    # Pilot channel mappings
    pilot_channels: dict[PilotId, PilotChannelConfig] = field(default_factory=dict)

    # Uncertainty & quality thresholds
    min_usable_quality: float = 0.40
    min_face_confidence: float = 0.50
    min_valid_frame_ratio: float = 0.85

    # Duration and temporal windows (virtual time milliseconds)
    min_observation_duration_ms: int = 1_000
    min_closed_window_ms: int = 3_000
    min_open_window_ms: int = 1_000
    max_gap_ms: int = 1_500

    # Geometry / EAR thresholds
    eye_closed_ear_threshold: float = 0.20
    eye_open_ear_threshold: float = 0.25

    # Live frame freshness (monotonic wall-time milliseconds)
    max_frame_age_ms: int = 2_000

    def __post_init__(self) -> None:
        if not self.pilot_channels:
            # Default: separate channels configured
            self.pilot_channels = {
                PilotId.PILOT_1: PilotChannelConfig(
                    pilot_id=PilotId.PILOT_1,
                    roi=NormalizedROI(0.0, 0.0, 0.5, 1.0),
                    enabled=True,
                ),
                PilotId.PILOT_2: PilotChannelConfig(
                    pilot_id=PilotId.PILOT_2,
                    roi=NormalizedROI(0.5, 0.0, 1.0, 1.0),
                    enabled=True,
                ),
            }
        self.validate()

    def validate(self) -> None:
        import math

        for name, val in [
            ("min_usable_quality", self.min_usable_quality),
            ("min_face_confidence", self.min_face_confidence),
            ("min_valid_frame_ratio", self.min_valid_frame_ratio),
            ("eye_closed_ear_threshold", self.eye_closed_ear_threshold),
            ("eye_open_ear_threshold", self.eye_open_ear_threshold),
        ]:
            if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
                raise ValueError(f"{name} must be a finite number")

        if not (0.0 < self.min_usable_quality <= 1.0):
            raise ValueError("min_usable_quality must be strictly positive in (0.0, 1.0]")
        if not (0.0 < self.min_face_confidence <= 1.0):
            raise ValueError("min_face_confidence must be strictly positive in (0.0, 1.0]")
        if not (0.5 <= self.min_valid_frame_ratio <= 1.0):
            raise ValueError("min_valid_frame_ratio must be in [0.5, 1.0]")
        if not (0.0 <= self.eye_closed_ear_threshold < self.eye_open_ear_threshold <= 1.0):
            raise ValueError(
                "eye_closed_ear_threshold must be strictly less than eye_open_ear_threshold and both in [0.0, 1.0]"
            )

        # Minimum evidence duration safeguards: prevent 0-duration single-sample triggers
        if self.min_observation_duration_ms < 500:
            raise ValueError(
                f"min_observation_duration_ms must be >= 500 ms to prevent single-sample triggers (got {self.min_observation_duration_ms})"
            )
        if self.min_closed_window_ms < 1_000:
            raise ValueError(
                f"min_closed_window_ms must be >= 1000 ms to enforce sustained closure evidence (got {self.min_closed_window_ms})"
            )
        if self.min_closed_window_ms < self.min_observation_duration_ms:
            raise ValueError("min_closed_window_ms must be >= min_observation_duration_ms")
        if self.min_open_window_ms < 500:
            raise ValueError("min_open_window_ms must be >= 500 ms")
        if self.max_gap_ms < 100:
            raise ValueError("max_gap_ms must be >= 100 ms")
        if self.max_frame_age_ms < 100:
            raise ValueError("max_frame_age_ms must be >= 100 ms")

        # Non-overlap validation if both pilots share the same source and have ROIs
        ch1 = self.pilot_channels.get(PilotId.PILOT_1)
        ch2 = self.pilot_channels.get(PilotId.PILOT_2)
        if ch1 and ch2 and ch1.enabled and ch2.enabled:
            same_source = (ch1.camera_index == ch2.camera_index and ch1.video_path == ch2.video_path)
            if same_source and ch1.roi is not None and ch2.roi is not None:
                if ch1.roi.overlaps(ch2.roi):
                    raise ValueError(
                        f"Pilot 1 and Pilot 2 ROIs cannot overlap when sharing the same source! "
                        f"P1 ROI: {ch1.roi}, P2 ROI: {ch2.roi}"
                    )

    @classmethod
    def single_pilot(cls, monitored_pilot: PilotId = PilotId.PILOT_1) -> VisionConfig:
        """Create a configuration where only one pilot is monitored with full frame."""
        other_pilot = PilotId.PILOT_2 if monitored_pilot == PilotId.PILOT_1 else PilotId.PILOT_1
        return cls(
            pilot_channels={
                monitored_pilot: PilotChannelConfig(
                    pilot_id=monitored_pilot,
                    roi=NormalizedROI(0.0, 0.0, 1.0, 1.0),
                    enabled=True,
                ),
                other_pilot: PilotChannelConfig(
                    pilot_id=other_pilot,
                    roi=None,
                    enabled=False,
                ),
            }
        )

    @classmethod
    def split_frame(cls) -> VisionConfig:
        """Standard dual-pilot split frame (left half for Pilot 1, right half for Pilot 2)."""
        return cls(
            pilot_channels={
                PilotId.PILOT_1: PilotChannelConfig(
                    pilot_id=PilotId.PILOT_1,
                    roi=NormalizedROI(0.0, 0.0, 0.5, 1.0),
                    enabled=True,
                ),
                PilotId.PILOT_2: PilotChannelConfig(
                    pilot_id=PilotId.PILOT_2,
                    roi=NormalizedROI(0.5, 0.0, 1.0, 1.0),
                    enabled=True,
                ),
            }
        )
