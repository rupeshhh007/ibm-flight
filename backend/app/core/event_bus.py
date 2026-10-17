from collections.abc import Sequence

from app.contracts.models import StoredEvent


class InMemoryEventPublisher:
    """P0 publisher. Race-safe SSE fan-out is intentionally deferred to P1."""

    def __init__(self) -> None:
        self.published: list[StoredEvent] = []

    def publish(self, events: Sequence[StoredEvent]) -> None:
        self.published.extend(events)


class InertRemoteSyncAdapter:
    def sync(self, events: Sequence[StoredEvent]) -> int:
        return 0
