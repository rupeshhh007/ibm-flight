from datetime import datetime
from uuid import UUID, uuid4

from app.contracts.enums import (
    AuthorizationSource,
    DecisionResult,
    FlightPhase,
    SentinelState,
    SimulatorActionType,
)
from app.contracts.models import AircraftTelemetry, SentinelDecision, SimulatorActionPayload


class MockAircraftSimulator:
    def __init__(self) -> None:
        self._run_id: UUID | None = None
        self._scenario_id: str | None = None
        self._telemetry: AircraftTelemetry | None = None
        self._last_action: SimulatorActionPayload | None = None

    def _telemetry_at(self, when: datetime) -> AircraftTelemetry:
        return AircraftTelemetry(
            aircraft_id="AEROGUARD-SIM-001",
            simulation_time=when,
            altitude_ft=35_000.0,
            airspeed_kts=450.0,
            heading_deg=90.0,
            latitude=19.0760,
            longitude=72.8777,
            flight_phase=FlightPhase.CRUISE,
            active_warning_codes=[],
        )

    def start(self, scenario_run_id: UUID, scenario_id: str, started_at: datetime) -> AircraftTelemetry:
        self._run_id = scenario_run_id
        self._scenario_id = scenario_id
        self._last_action = None
        self._telemetry = self._telemetry_at(started_at)
        return self._telemetry

    def advance(self, scenario_run_id: UUID, simulation_time: datetime) -> AircraftTelemetry:
        self._require_run(scenario_run_id)
        self._telemetry = self._telemetry_at(simulation_time)
        return self._telemetry

    def apply_action(
        self,
        scenario_run_id: UUID,
        action: SimulatorActionType,
        authorization: SentinelDecision,
        applied_at: datetime,
    ) -> SimulatorActionPayload:
        self._require_run(scenario_run_id)
        if not isinstance(action, SimulatorActionType):
            raise ValueError("simulator action must be a canonical SimulatorActionType")
        if self._last_action is not None:
            raise ValueError("a symbolic simulator action already executed for this run")
        if (
            authorization.scenario_run_id != scenario_run_id
            or authorization.action_type != action
            or authorization.sentinel_state != SentinelState.SIM_ACTION_RUNNING
            or authorization.authorization_source == AuthorizationSource.NONE
            or authorization.result != DecisionResult.APPROVED
        ):
            raise ValueError("simulator rejected invalid authorization context")
        self._last_action = SimulatorActionPayload(
            action_id=uuid4(),
            scenario_run_id=scenario_run_id,
            action_type=action,
            authorization_source=authorization.authorization_source,
            authorized=True,
            result=DecisionResult.EXECUTED,
            reason="Validated symbolic simulation action; no operational aircraft control.",
            applied_at=applied_at,
        )
        return self._last_action

    def reset(self, scenario_run_id: UUID, scenario_id: str, reset_at: datetime) -> AircraftTelemetry:
        return self.start(scenario_run_id, scenario_id, reset_at)

    def _require_run(self, scenario_run_id: UUID) -> None:
        if self._run_id != scenario_run_id:
            raise ValueError("simulator rejected stale scenario_run_id")
