from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuardianPolicy:
    """Deterministic demo heuristics for the enhanced Guardian.

    These values are simulation parameters, not validated aviation or medical
    thresholds. Time advances only when Guardian receives an observation.
    """

    minimum_observation_quality: float = 0.80
    minimum_independent_spacing_ms: int = 500
    evidence_window_ms: int = 10_000
    concerns_required_per_pilot: int = 2
    awaiting_ack_concerns: int = 2
    acknowledgement_grace_ms: int = 1_000
    recovery_observations_required_per_pilot: int = 2
    max_evidence_per_pilot: int = 8
    max_processed_events: int = 256
    max_acknowledgements: int = 128

    def __post_init__(self) -> None:
        if not 0.0 <= self.minimum_observation_quality <= 1.0:
            raise ValueError("minimum_observation_quality must be between 0 and 1")
        if self.minimum_independent_spacing_ms <= 0:
            raise ValueError("minimum_independent_spacing_ms must be positive")
        if self.evidence_window_ms <= 0:
            raise ValueError("evidence_window_ms must be positive")
        if self.concerns_required_per_pilot < 2:
            raise ValueError("concerns_required_per_pilot must be at least 2")
        if self.concerns_required_per_pilot > 32:
            raise ValueError("concerns_required_per_pilot cannot exceed the incident evidence limit")
        if not 2 <= self.awaiting_ack_concerns <= self.concerns_required_per_pilot:
            raise ValueError("awaiting_ack_concerns must be between 2 and concerns_required_per_pilot")
        if not 0 <= self.acknowledgement_grace_ms <= self.evidence_window_ms:
            raise ValueError("acknowledgement_grace_ms must be within the evidence window")
        if self.recovery_observations_required_per_pilot <= 0:
            raise ValueError("recovery_observations_required_per_pilot must be positive")
        if self.max_evidence_per_pilot < self.concerns_required_per_pilot:
            raise ValueError("max_evidence_per_pilot cannot be smaller than the concern threshold")
        if self.max_evidence_per_pilot > 32:
            raise ValueError("max_evidence_per_pilot cannot exceed 32 per pilot")
        if self.max_processed_events < self.max_evidence_per_pilot * 2:
            raise ValueError("max_processed_events must retain at least both pilots' evidence capacity")
        if self.max_acknowledgements <= 0:
            raise ValueError("max_acknowledgements must be positive")
        minimum_window = self.minimum_independent_spacing_ms * (self.concerns_required_per_pilot - 1)
        if self.evidence_window_ms < minimum_window:
            raise ValueError("evidence_window_ms is too short for the configured independent observations")
