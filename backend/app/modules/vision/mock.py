from datetime import datetime

from app.contracts.enums import PilotId, PilotObservationStatus
from app.contracts.models import PilotObservation


class MockVisionAdapter:
    def __init__(self) -> None:
        self._scenario_id = "normal_flight"

    def configure_scenario(self, scenario_id: str) -> None:
        self._scenario_id = scenario_id

    def observe(self, pilot_id: PilotId, observed_at: datetime) -> PilotObservation:
        status = PilotObservationStatus.RESPONSIVE
        camera_available = True
        face_visible = True
        eyes_closed = False
        quality = 0.95
        if self._scenario_id in {"dual_pilot_atc_connected", "dual_pilot_atc_disconnected"}:
            status = PilotObservationStatus.POSSIBLY_UNRESPONSIVE
            eyes_closed = True
            quality = 0.90
        elif self._scenario_id == "single_pilot_unresponsive" and pilot_id == PilotId.PILOT_1:
            status = PilotObservationStatus.POSSIBLY_UNRESPONSIVE
            eyes_closed = True
            quality = 0.90
        elif self._scenario_id == "camera_obstructed":
            status = PilotObservationStatus.UNKNOWN
            camera_available = False
            face_visible = False
            quality = 0.0
        return PilotObservation(
            pilot_id=pilot_id,
            observed_at=observed_at,
            observation_status=status,
            camera_available=camera_available,
            face_visible=face_visible,
            eyes_closed=eyes_closed,
            observation_duration_ms=1_000,
            observation_quality=quality,
        )
