from datetime import datetime, timedelta, timezone


class VirtualClock:
    def __init__(self, initial: datetime | None = None) -> None:
        self._now = initial or datetime(2026, 1, 1, tzinfo=timezone.utc)
        self._validate(self._now)

    @staticmethod
    def _validate(value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("virtual clock requires an aware datetime")

    def now(self) -> datetime:
        return self._now

    def advance(self, delta_ms: int) -> datetime:
        if not 1 <= delta_ms <= 600_000:
            raise ValueError("delta_ms must be between 1 and 600000")
        self._now += timedelta(milliseconds=delta_ms)
        return self._now

    def reset(self, initial: datetime | None = None) -> datetime:
        self._now = initial or datetime(2026, 1, 1, tzinfo=timezone.utc)
        self._validate(self._now)
        return self._now
