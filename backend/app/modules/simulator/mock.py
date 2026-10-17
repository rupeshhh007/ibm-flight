from datetime import datetime, timezone
from math import sin, tau
from uuid import UUID, uuid4

from app.contracts.enums import (
    AuthorizationSource,
    DecisionResult,
    FlightPhase,
    SentinelState,
    SimulatorActionType,
)
from app.contracts.models import AircraftTelemetry, SentinelDecision, SimulatorActionPayload
from app.scenarios.catalog import get_scenario


class MockAircraftSimulator:
    """Deterministic synthetic telemetry and symbolic-action test double.

    Telemetry is derived only from the caller-supplied virtual timestamp. The
    bounded oscillations make time progression visible without modelling an
    operational route, navigation system, or real aircraft dynamics.
    """

    _BASE_ALTITUDE_FT = 35_000.0
    _BASE_AIRSPEED_KTS = 450.0
    _ALTITUDE_AMPLITUDE_FT = 120.0
    _AIRSPEED_AMPLITUDE_KTS = 6.0
    _ALTITUDE_PERIOD_SECONDS = 120.0
    _AIRSPEED_PERIOD_SECONDS = 90.0

    def __init__(self) -> None:
        self._run_id: UUID | None = None
        self._scenario_id: str | None = None
        self._started_at: datetime | None = None
        self._telemetry: AircraftTelemetry | None = None
        self._last_action: SimulatorActionPayload | None = None
        self._action_history: list[SimulatorActionPayload] = []
        self._executed_authorization_ids: set[UUID] = set()

    @staticmethod
    def _utc(value: datetime, field_name: str = "simulation time") -> datetime:
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} must be a timezone-aware datetime")
        return value.astimezone(timezone.utc)

    @classmethod
    def _telemetry_at(cls, when: datetime, started_at: datetime) -> AircraftTelemetry:
        elapsed_seconds = (when - started_at).total_seconds()
        altitude_ft = cls._BASE_ALTITUDE_FT + cls._ALTITUDE_AMPLITUDE_FT * sin(
            tau * elapsed_seconds / cls._ALTITUDE_PERIOD_SECONDS
        )
        airspeed_kts = cls._BASE_AIRSPEED_KTS + cls._AIRSPEED_AMPLITUDE_KTS * sin(
            tau * elapsed_seconds / cls._AIRSPEED_PERIOD_SECONDS
        )
        return AircraftTelemetry(
            aircraft_id="AEROGUARD-SIM-001",
            simulation_time=when,
            altitude_ft=altitude_ft,
            airspeed_kts=airspeed_kts,
            heading_deg=90.0,
            latitude=19.0760,
            longitude=72.8777,
            flight_phase=FlightPhase.CRUISE,
            active_warning_codes=[],
        )

    def start(self, scenario_run_id: UUID, scenario_id: str, started_at: datetime) -> AircraftTelemetry:
        if not isinstance(scenario_run_id, UUID):
            raise ValueError("scenario_run_id must be a UUID")
        definition = get_scenario(scenario_id)
        normalized_start = self._utc(started_at)
        telemetry = self._telemetry_at(normalized_start, normalized_start)
        self._run_id = scenario_run_id
        self._scenario_id = definition.metadata.scenario_id
        self._started_at = normalized_start
        self._last_action = None
        self._action_history = []
        self._executed_authorization_ids = set()
        self._telemetry = telemetry
        return telemetry.model_copy(deep=True)

    def advance(self, scenario_run_id: UUID, simulation_time: datetime) -> AircraftTelemetry:
        self._require_run(scenario_run_id)
        if self._started_at is None or self._telemetry is None:
            raise ValueError("simulator has not been started")
        normalized_time = self._utc(simulation_time)
        if normalized_time < self._telemetry.simulation_time:
            raise ValueError("simulation_time cannot move backwards")
        telemetry = self._telemetry_at(normalized_time, self._started_at)
        self._telemetry = telemetry
        return telemetry.model_copy(deep=True)

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
        candidate = self._validated_authorization(authorization)
        normalized_applied_at = self._utc(applied_at, "applied_at")
        if self._started_at is None or self._telemetry is None:
            raise ValueError("simulator has not been started")
        if candidate.scenario_run_id != scenario_run_id:
            raise ValueError("authorization does not belong to the active scenario run")
        if candidate.action_type != action:
            raise ValueError("authorization does not match the requested simulator action")
        if candidate.authorization_source == AuthorizationSource.NONE:
            raise ValueError("authorization source NONE cannot execute a simulator action")
        if candidate.result != DecisionResult.APPROVED:
            raise ValueError("simulator action requires an APPROVED decision result")
        if candidate.sentinel_state != SentinelState.SIM_ACTION_RUNNING:
            raise ValueError("authorization is not in the SIM_ACTION_RUNNING Sentinel state")
        if candidate.executed_at < self._started_at:
            raise ValueError("authorization predates the active scenario run")
        if normalized_applied_at < self._telemetry.simulation_time:
            raise ValueError("applied_at cannot precede current simulation time")
        if candidate.decision_id in self._executed_authorization_ids:
            raise ValueError("authorization decision was already executed")
        if self._last_action is not None:
            raise ValueError("the active simulator run is already in its terminal action state")

        # Construct and validate the complete canonical result before committing
        # any run-local state. The action itself remains symbolic: no flight
        # dynamics, route, navigation, or real aircraft-control values change.
        payload = SimulatorActionPayload(
            action_id=uuid4(),
            scenario_run_id=scenario_run_id,
            action_type=action,
            authorization_source=candidate.authorization_source,
            authorized=True,
            result=DecisionResult.EXECUTED,
            reason="Validated symbolic simulation action; no operational aircraft control.",
            applied_at=normalized_applied_at,
        )
        stored = payload.model_copy(deep=True)
        self._action_history.append(stored)
        self._executed_authorization_ids.add(candidate.decision_id)
        self._last_action = stored
        return payload.model_copy(deep=True)

    def reset(self, scenario_run_id: UUID, scenario_id: str, reset_at: datetime) -> AircraftTelemetry:
        return self.start(scenario_run_id, scenario_id, reset_at)

    def _require_run(self, scenario_run_id: UUID) -> None:
        if self._run_id != scenario_run_id:
            raise ValueError("simulator rejected stale scenario_run_id")

    @staticmethod
    def _validated_authorization(authorization: SentinelDecision) -> SentinelDecision:
        if not isinstance(authorization, SentinelDecision):
            raise ValueError("simulator requires a canonical SentinelDecision")
        canonical_fields = (
            isinstance(getattr(authorization, "decision_id", None), UUID),
            isinstance(getattr(authorization, "scenario_run_id", None), UUID),
            isinstance(getattr(authorization, "incident_id", None), UUID),
            isinstance(getattr(authorization, "sentinel_state", None), SentinelState),
            isinstance(getattr(authorization, "action_type", None), SimulatorActionType),
            isinstance(getattr(authorization, "authorization_source", None), AuthorizationSource),
            isinstance(getattr(authorization, "result", None), DecisionResult),
            isinstance(getattr(authorization, "executed_at", None), datetime),
        )
        if not all(canonical_fields):
            raise ValueError("simulator requires a well-formed canonical SentinelDecision")
        try:
            return SentinelDecision.model_validate(authorization.model_dump())
        except (TypeError, ValueError) as exc:
            raise ValueError("simulator requires a well-formed canonical SentinelDecision") from exc
