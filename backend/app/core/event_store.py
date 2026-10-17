from __future__ import annotations

import sqlite3
import threading
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from app.contracts.models import CommandRecord, DomainEvent, StoredEvent


class SQLiteEventStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._initialize()

    def _initialize(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    scenario_run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_run_seq
                    ON events(scenario_run_id, seq);
                CREATE TABLE IF NOT EXISTS command_results (
                    command_id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                """
            )

    def append(self, events: Sequence[DomainEvent]) -> list[StoredEvent]:
        stored: list[StoredEvent] = []
        with self._lock, self._connection:
            for event in events:
                cursor = self._connection.execute(
                    "INSERT INTO events(event_id, scenario_run_id, event_type, event_json) VALUES (?, ?, ?, ?)",
                    (
                        str(event.event_id),
                        str(event.scenario_run_id),
                        event.event_type.value,
                        event.model_dump_json(),
                    ),
                )
                stored.append(StoredEvent(**event.model_dump(), seq=int(cursor.lastrowid)))
        return stored

    def read_after(self, after_seq: int, limit: int) -> list[StoredEvent]:
        if after_seq < 0:
            raise ValueError("after_seq must be non-negative")
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        with self._lock:
            rows = self._connection.execute(
                "SELECT seq, event_json FROM events WHERE seq > ? ORDER BY seq ASC LIMIT ?",
                (after_seq, limit),
            ).fetchall()
        result: list[StoredEvent] = []
        for row in rows:
            event = DomainEvent.model_validate_json(row["event_json"])
            result.append(StoredEvent(**event.model_dump(), seq=row["seq"]))
        return result

    def latest_seq(self) -> int:
        with self._lock:
            row = self._connection.execute("SELECT COALESCE(MAX(seq), 0) AS seq FROM events").fetchone()
        return int(row["seq"])

    def get_command(self, command_id: UUID) -> CommandRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT command_id, fingerprint, result_json FROM command_results WHERE command_id = ?",
                (str(command_id),),
            ).fetchone()
        return CommandRecord.model_validate(dict(row)) if row else None

    def record_command(self, record: CommandRecord) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO command_results(command_id, fingerprint, result_json) VALUES (?, ?, ?)",
                (str(record.command_id), record.fingerprint, record.result_json),
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()
