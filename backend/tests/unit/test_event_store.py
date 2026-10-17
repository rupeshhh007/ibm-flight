from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app.contracts.enums import EventSource, EventType
from app.contracts.models import CommandRecord, DomainEvent, ScenarioStartedPayload
from app.core.event_store import SQLiteEventStore


def _event(event_id=None) -> DomainEvent:
    run_id = uuid4()
    now = datetime.now(timezone.utc)
    return DomainEvent(
        event_id=event_id or uuid4(),
        event_type=EventType.SCENARIO_STARTED,
        occurred_at=now,
        source=EventSource.SCENARIO,
        scenario_run_id=run_id,
        correlation_id=uuid4(),
        payload=ScenarioStartedPayload(scenario_id="normal_flight", started_at=now),
    )


def test_events_survive_reopen_and_sequences_increase(tmp_path: Path) -> None:
    path = tmp_path / "events.db"
    store = SQLiteEventStore(path)
    stored = store.append([_event(), _event()])
    assert [item.seq for item in stored] == [1, 2]
    store.close()
    reopened = SQLiteEventStore(path)
    assert [item.seq for item in reopened.read_after(0, 100)] == [1, 2]
    assert [item.seq for item in reopened.read_after(1, 100)] == [2]
    reopened.close()


def test_duplicate_event_id_is_rejected(tmp_path: Path) -> None:
    store = SQLiteEventStore(tmp_path / "events.db")
    event_id = uuid4()
    store.append([_event(event_id)])
    with pytest.raises(Exception):
        store.append([_event(event_id)])
    assert store.latest_seq() == 1
    store.close()


def test_command_result_survives_reopen(tmp_path: Path) -> None:
    path = tmp_path / "commands.db"
    command_id = uuid4()
    store = SQLiteEventStore(path)
    store.record_command(CommandRecord(command_id=command_id, fingerprint="abc", result_json="{}"))
    store.close()
    reopened = SQLiteEventStore(path)
    assert reopened.get_command(command_id) == CommandRecord(
        command_id=command_id,
        fingerprint="abc",
        result_json="{}",
    )
    reopened.close()
