from app.contracts.enums import PilotId

from .catalog import ScenarioDefinition


class ScenarioRunner:
    def __init__(self, definition: ScenarioDefinition) -> None:
        self.definition = definition
        self._schedule = self._validated_schedule(definition.observation_schedule)
        self.elapsed_ms = 0
        self._cursor = 0

    @staticmethod
    def _validated_schedule(
        schedule: tuple[tuple[int, PilotId], ...],
    ) -> tuple[tuple[int, PilotId], ...]:
        seen: set[tuple[int, PilotId]] = set()
        indexed: list[tuple[int, int, PilotId]] = []
        for position, entry in enumerate(schedule):
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise ValueError("scenario schedule entries must be (time_ms, pilot_id) tuples")
            scheduled_time, pilot_id = entry
            if type(scheduled_time) is not int or scheduled_time <= 0:
                raise ValueError("scheduled time_ms must be a positive integer")
            if not isinstance(pilot_id, PilotId):
                raise ValueError("scheduled pilot_id must be a canonical PilotId")
            key = (scheduled_time, pilot_id)
            if key in seen:
                raise ValueError("scenario schedule contains a duplicate observation")
            seen.add(key)
            indexed.append((scheduled_time, position, pilot_id))
        indexed.sort(key=lambda item: (item[0], item[1]))
        return tuple((scheduled_time, pilot_id) for scheduled_time, _, pilot_id in indexed)

    def advance(self, delta_ms: int) -> list[PilotId]:
        if type(delta_ms) is not int or not 1 <= delta_ms <= 600_000:
            raise ValueError("delta_ms must be between 1 and 600000")
        target = self.elapsed_ms + delta_ms
        due: list[PilotId] = []
        cursor = self._cursor
        while cursor < len(self._schedule):
            scheduled_time, pilot_id = self._schedule[cursor]
            if scheduled_time > target:
                break
            due.append(pilot_id)
            cursor += 1
        self._cursor = cursor
        self.elapsed_ms = target
        return due
