from datetime import datetime, timezone
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.contracts.enums import EventSource, EventType, PilotId, PilotObservationStatus
from app.contracts.interfaces import (
    AircraftSimulator,
    Clock,
    EventPublisher,
    EventStore,
    GuardianAgent,
    RemoteSyncAdapter,
    SentinelAgent,
    VisionAdapter,
)
from app.contracts.models import ATCDecision, AircraftTelemetry, DomainEvent, PilotObservation
from app.core.clock import VirtualClock
from app.core.event_bus import InMemoryEventPublisher, InertRemoteSyncAdapter
from app.core.event_store import SQLiteEventStore
from app.modules.guardian import MockGuardianAgent
from app.modules.sentinel import MockSentinelAgent
from app.modules.simulator import MockAircraftSimulator
from app.modules.vision import MockVisionAdapter


FIXTURES = Path(__file__).parents[3] / "contracts" / "fixtures"


def test_valid_event_fixture_roundtrips() -> None:
    raw = (FIXTURES / "pilot_observation_event.json").read_text(encoding="utf-8")
    event = DomainEvent.model_validate_json(raw)
    assert DomainEvent.model_validate_json(event.model_dump_json()) == event


def test_valid_command_fixture_roundtrips() -> None:
    raw = (FIXTURES / "atc_decision.json").read_text(encoding="utf-8")
    decision = ATCDecision.model_validate_json(raw)
    assert ATCDecision.model_validate_json(decision.model_dump_json()) == decision


def test_event_type_payload_mismatch_is_rejected() -> None:
    observation = PilotObservation(
        pilot_id=PilotId.PILOT_1,
        observed_at=datetime.now(timezone.utc),
        observation_status=PilotObservationStatus.RESPONSIVE,
        camera_available=True,
        face_visible=True,
        eyes_closed=False,
        observation_duration_ms=100,
        observation_quality=1.0,
    )
    with pytest.raises(ValidationError, match="requires payload AircraftTelemetry"):
        DomainEvent(
            event_id=uuid4(),
            event_type=EventType.TELEMETRY_UPDATED,
            occurred_at=datetime.now(timezone.utc),
            source=EventSource.VISION,
            scenario_run_id=uuid4(),
            correlation_id=uuid4(),
            payload=observation,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("observation_quality", 1.1),
        ("observation_duration_ms", -1),
        ("observed_at", datetime(2026, 1, 1)),
    ],
)
def test_invalid_observation_values_are_rejected(field: str, value: object) -> None:
    data = {
        "pilot_id": PilotId.PILOT_1,
        "observed_at": datetime.now(timezone.utc),
        "observation_status": PilotObservationStatus.RESPONSIVE,
        "camera_available": True,
        "face_visible": True,
        "eyes_closed": False,
        "observation_duration_ms": 100,
        "observation_quality": 0.5,
    }
    data[field] = value
    with pytest.raises(ValidationError):
        PilotObservation(**data)


def test_unknown_enum_extra_property_and_coordinates_are_rejected() -> None:
    with pytest.raises(ValidationError):
        PilotObservation.model_validate(
            {
                "pilot_id": "PILOT_3",
                "observed_at": datetime.now(timezone.utc),
                "observation_status": "RESPONSIVE",
                "camera_available": True,
                "face_visible": True,
                "eyes_closed": False,
                "observation_duration_ms": 10,
                "observation_quality": 0.5,
                "diagnosis": "forbidden",
            }
        )
    with pytest.raises(ValidationError):
        PilotObservation(
            pilot_id=PilotId.PILOT_1,
            observed_at=datetime.now(timezone.utc),
            observation_status=PilotObservationStatus.RESPONSIVE,
            camera_available=True,
            face_visible=True,
            eyes_closed=False,
            observation_duration_ms=10,
            observation_quality=0.5,
            diagnosis="forbidden",
        )
    with pytest.raises(ValidationError):
        AircraftTelemetry(
            aircraft_id="SIM",
            simulation_time=datetime.now(timezone.utc),
            altitude_ft=1_000,
            airspeed_kts=100,
            heading_deg=90,
            latitude=91,
            longitude=0,
            flight_phase="CRUISE",
            active_warning_codes=[],
        )


def test_mock_implementations_conform_to_runtime_protocols(tmp_path: Path) -> None:
    assert isinstance(MockVisionAdapter(), VisionAdapter)
    assert isinstance(MockAircraftSimulator(), AircraftSimulator)
    assert isinstance(MockGuardianAgent(), GuardianAgent)
    assert isinstance(MockSentinelAgent(), SentinelAgent)
    assert isinstance(VirtualClock(), Clock)
    store = SQLiteEventStore(tmp_path / "protocol.db")
    assert isinstance(store, EventStore)
    store.close()
    assert isinstance(InMemoryEventPublisher(), EventPublisher)
    assert isinstance(InertRemoteSyncAdapter(), RemoteSyncAdapter)


def test_invalid_uuid_in_json_is_rejected() -> None:
    raw = (FIXTURES / "pilot_observation_event.json").read_text(encoding="utf-8")
    with pytest.raises(ValidationError):
        DomainEvent.model_validate_json(raw.replace("11111111-1111-4111-8111-111111111111", "not-a-uuid"))
