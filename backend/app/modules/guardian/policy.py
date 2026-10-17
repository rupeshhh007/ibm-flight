from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


_MAX_EVIDENCE_WINDOW_MS = 86_400_000
_MAX_OBSERVATION_SPACING_MS = 600_000
_MAX_RETAINED_IDENTIFIERS = 100_000


def _require_int(name: str, value: object, *, minimum: int, maximum: int) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


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
        quality = self.minimum_observation_quality
        if isinstance(quality, bool) or not isinstance(quality, (int, float)):
            raise ValueError("minimum_observation_quality must be a finite number")
        quality = float(quality)
        if not isfinite(quality) or not 0.0 <= quality <= 1.0:
            raise ValueError("minimum_observation_quality must be between 0 and 1")
        object.__setattr__(self, "minimum_observation_quality", quality)

        spacing_ms = _require_int(
            "minimum_independent_spacing_ms",
            self.minimum_independent_spacing_ms,
            minimum=1,
            maximum=_MAX_OBSERVATION_SPACING_MS,
        )
        evidence_window_ms = _require_int(
            "evidence_window_ms",
            self.evidence_window_ms,
            minimum=1,
            maximum=_MAX_EVIDENCE_WINDOW_MS,
        )
        concerns_required = _require_int(
            "concerns_required_per_pilot",
            self.concerns_required_per_pilot,
            minimum=2,
            maximum=32,
        )
        awaiting_ack_concerns = _require_int(
            "awaiting_ack_concerns",
            self.awaiting_ack_concerns,
            minimum=2,
            maximum=32,
        )
        if awaiting_ack_concerns > concerns_required:
            raise ValueError("awaiting_ack_concerns must be between 2 and concerns_required_per_pilot")
        acknowledgement_grace_ms = _require_int(
            "acknowledgement_grace_ms",
            self.acknowledgement_grace_ms,
            minimum=0,
            maximum=_MAX_EVIDENCE_WINDOW_MS,
        )
        if acknowledgement_grace_ms > evidence_window_ms:
            raise ValueError("acknowledgement_grace_ms must be within the evidence window")
        recovery_required = _require_int(
            "recovery_observations_required_per_pilot",
            self.recovery_observations_required_per_pilot,
            minimum=1,
            maximum=32,
        )
        max_evidence = _require_int(
            "max_evidence_per_pilot",
            self.max_evidence_per_pilot,
            minimum=2,
            maximum=32,
        )
        if max_evidence < concerns_required:
            raise ValueError("max_evidence_per_pilot cannot be smaller than the concern threshold")
        max_processed_events = _require_int(
            "max_processed_events",
            self.max_processed_events,
            minimum=1,
            maximum=_MAX_RETAINED_IDENTIFIERS,
        )
        if max_processed_events < max_evidence * 2:
            raise ValueError("max_processed_events must retain at least both pilots' evidence capacity")
        _require_int(
            "max_acknowledgements",
            self.max_acknowledgements,
            minimum=1,
            maximum=_MAX_RETAINED_IDENTIFIERS,
        )
        minimum_window = spacing_ms * (concerns_required - 1)
        if evidence_window_ms < minimum_window:
            raise ValueError("evidence_window_ms is too short for the configured independent observations")
        minimum_recovery_window = spacing_ms * (recovery_required - 1)
        if evidence_window_ms < minimum_recovery_window:
            raise ValueError("evidence_window_ms is too short for the configured recovery observations")
