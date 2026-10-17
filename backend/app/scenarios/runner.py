from app.contracts.enums import PilotId

from .catalog import ScenarioDefinition


class ScenarioRunner:
    def __init__(self, definition: ScenarioDefinition) -> None:
        self.definition = definition
        self.elapsed_ms = 0
        self._processed: set[tuple[int, PilotId]] = set()

    def advance(self, delta_ms: int) -> list[PilotId]:
        if not 1 <= delta_ms <= 600_000:
            raise ValueError("delta_ms must be between 1 and 600000")
        target = self.elapsed_ms + delta_ms
        due: list[PilotId] = []
        for scheduled_time, pilot_id in self.definition.observation_schedule:
            key = (scheduled_time, pilot_id)
            if self.elapsed_ms < scheduled_time <= target and key not in self._processed:
                self._processed.add(key)
                due.append(pilot_id)
        self.elapsed_ms = target
        return due
