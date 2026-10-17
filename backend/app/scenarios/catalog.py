from dataclasses import dataclass

from app.contracts.enums import PilotId
from app.contracts.models import ScenarioMetadata


@dataclass(frozen=True)
class ScenarioDefinition:
    metadata: ScenarioMetadata
    atc_connected: bool
    observation_schedule: tuple[tuple[int, PilotId], ...]


def _rounds(*times: int) -> tuple[tuple[int, PilotId], ...]:
    return tuple((time_ms, pilot_id) for time_ms in times for pilot_id in PilotId)


SCENARIOS: dict[str, ScenarioDefinition] = {
    "normal_flight": ScenarioDefinition(
        ScenarioMetadata(
            scenario_id="normal_flight",
            name="Normal flight",
            description="Both synthetic pilots remain responsive.",
            p0_behavior="Complete deterministic no-escalation path.",
        ),
        True,
        _rounds(1_000, 2_000),
    ),
    "single_pilot_unresponsive": ScenarioDefinition(
        ScenarioMetadata(
            scenario_id="single_pilot_unresponsive",
            name="Single pilot concern",
            description="Pilot 1 has synthetic concern observations while Pilot 2 remains responsive.",
            p0_behavior="Safety-negative path; no dual-pilot incident or action.",
        ),
        True,
        _rounds(1_000, 2_000),
    ),
    "dual_pilot_atc_connected": ScenarioDefinition(
        ScenarioMetadata(
            scenario_id="dual_pilot_atc_connected",
            name="Dual pilot concern with simulated ATC",
            description="Repeated synthetic concern evidence requires explicit simulated ATC approval.",
            p0_behavior="Complete Guardian-to-Sentinel-to-simulator approval-gated path.",
        ),
        True,
        _rounds(1_000, 2_000),
    ),
    "dual_pilot_atc_disconnected": ScenarioDefinition(
        ScenarioMetadata(
            scenario_id="dual_pilot_atc_disconnected",
            name="Dual pilot concern without simulated ATC",
            description="Stronger fallback behavior is reserved for P1; disconnect alone never acts.",
            p0_behavior="Deterministic escalation with no automatic fallback action.",
        ),
        False,
        _rounds(1_000, 2_000),
    ),
    "camera_obstructed": ScenarioDefinition(
        ScenarioMetadata(
            scenario_id="camera_obstructed",
            name="Camera obstructed",
            description="Unavailable synthetic camera observations remain UNKNOWN.",
            p0_behavior="Complete safety-negative path with no incident/action.",
        ),
        True,
        _rounds(1_000, 2_000),
    ),
}


def list_scenarios() -> list[ScenarioMetadata]:
    return [definition.metadata.model_copy(deep=True) for definition in SCENARIOS.values()]


def get_scenario(scenario_id: str) -> ScenarioDefinition:
    try:
        definition = SCENARIOS[scenario_id]
    except KeyError as exc:
        raise ValueError(f"unknown scenario_id: {scenario_id}") from exc
    return ScenarioDefinition(
        metadata=definition.metadata.model_copy(deep=True),
        atc_connected=definition.atc_connected,
        observation_schedule=definition.observation_schedule,
    )
