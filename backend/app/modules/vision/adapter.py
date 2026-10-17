"""
RealVisionAdapter: Uncertainty-aware pilot monitoring adapter implementing the frozen VisionAdapter protocol.

SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.contracts.enums import PilotId, PilotObservationStatus
from app.contracts.models import PilotObservation
from .config import VisionConfig
from .evidence import PilotEvidenceWindow
from .sources import FrameSource, ReplayLandmarkSource

logger = logging.getLogger(__name__)


class RealVisionAdapter:
    """
    Modular, testable Vision subsystem adapter implementing VisionAdapter.
    Produces canonical PilotObservation payloads with strict separation between PILOT_1 and PILOT_2.
    """

    def __init__(
        self,
        config: VisionConfig | None = None,
        source: FrameSource | None = None,
    ) -> None:
        self._config = config or VisionConfig()
        self._source: FrameSource = source or ReplayLandmarkSource()
        self._windows: dict[PilotId, PilotEvidenceWindow] = {
            PilotId.PILOT_1: PilotEvidenceWindow(),
            PilotId.PILOT_2: PilotEvidenceWindow(),
        }

    @property
    def config(self) -> VisionConfig:
        return self._config

    @property
    def source(self) -> FrameSource:
        return self._source

    def configure_scenario(self, scenario_id: str) -> None:
        """Reset pilot histories and reconfigure the underlying source."""
        for window in self._windows.values():
            window.reset()
        self._source.configure_scenario(scenario_id)

    def observe(self, pilot_id: PilotId, observed_at: datetime) -> PilotObservation:
        """
        Produce a canonical PilotObservation for the requested pilot at the virtual timestamp.
        """
        # Ensure timestamp is normalized timezone-aware UTC
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        else:
            observed_at = observed_at.astimezone(timezone.utc)

        # Invariant: Channel must be explicitly configured and enabled
        channel = self._config.pilot_channels.get(pilot_id)
        if channel is None or not channel.enabled:
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

        try:
            # Acquire frame evidence for this specific pilot
            sample = self._source.get_sample(pilot_id, observed_at, self._config)

            # Record in the isolated per-pilot evidence window
            window = self._windows[pilot_id]
            window.add_sample(sample)

            # Evaluate window and apply conservative uncertainty rules
            return window.evaluate(pilot_id, observed_at, self._config)
        except Exception as exc:
            logger.warning("Error evaluating vision observation for %s: %s", pilot_id, exc)
            window = self._windows.get(pilot_id)
            if window is not None:
                window.reset()
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

    def close(self) -> None:
        """Idempotently close underlying sources and release resources."""
        if hasattr(self._source, "close"):
            try:
                self._source.close()
            except Exception as exc:
                logger.warning("Error closing vision source: %s", exc)
