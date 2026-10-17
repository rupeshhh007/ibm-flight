"""
Private typed configuration for the Vision subsystem.

SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.contracts.enums import PilotId
from .geometry import NormalizedROI


def canonical_source_key(
    camera_index: int | None = None,
    video_path: Path | str | None = None,
) -> tuple[str, int | str]:
    """
    Return a canonical tuple identifying a capture source:
    - ("video", normalized_path_str) if video_path is provided
    - ("camera", camera_index or 0) if camera_index is provided (or defaults to 0 if None)
    """
    if video_path is not None:
        return ("video", str(Path(video_path)))
    return ("camera", 0 if camera_index is None else camera_index)


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

    def canonical_source_key(self) -> tuple[str, int | str]:
        """Return the canonical source identity for this channel."""
        return canonical_source_key(self.camera_index, self.video_path)


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
            ("min_observation_duration_ms", self.min_observation_duration_ms),
            ("min_closed_window_ms", self.min_closed_window_ms),
            ("min_open_window_ms", self.min_open_window_ms),
            ("max_gap_ms", self.max_gap_ms),
            ("max_frame_age_ms", self.max_frame_age_ms),
        ]:
            if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
                raise ValueError(f"{name} must be a finite number")

        # Validate that pilot_channels keys match each PilotChannelConfig's pilot_id
        for pid, ch in self.pilot_channels.items():
            if pid != ch.pilot_id:
                raise ValueError(
                    f"pilot_channels key '{pid}' does not match PilotChannelConfig.pilot_id '{ch.pilot_id}'"
                )

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

        # Mandatory unambiguous, non-overlapping ROI validation for shared sources
        ch1 = self.pilot_channels.get(PilotId.PILOT_1)
        ch2 = self.pilot_channels.get(PilotId.PILOT_2)
        if ch1 and ch2 and ch1.enabled and ch2.enabled:
            same_source = (ch1.canonical_source_key() == ch2.canonical_source_key())
            if same_source:
                if ch1.roi is None or ch2.roi is None:
                    raise ValueError(
                        "Pilot 1 and Pilot 2 share the same camera/video source and both are enabled; "
                        "both pilots MUST have explicit, disjoint non-overlapping ROIs configured "
                        "to prevent cross-pilot observation contamination."
                    )
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
