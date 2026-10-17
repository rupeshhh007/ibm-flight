"""SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.contracts.enums import (
    ATCDecisionType,
    AuthorizationSource,
    DecisionResult,
    GuardianState,
    IncidentType,
    SentinelState,
    SimulatorActionType,
)
from app.contracts.models import ATCDecision, GuardianIncident, SentinelDecision


class DeterministicSentinelAgent:
    """Guard a single incident lifecycle; execution belongs to the orchestrator.

    Identical pending redelivery returns a defensive copy of the original pending
    decision, including its ID and timestamp. A link change invalidates that
    pending response. Running/completed lifecycles reject all incident delivery.

    Retains the mock's reject-then-approve and conservative link-change behavior.
    Reconnect leaves STANDBY unchanged: the orchestrator must redeliver the
    retained identical, still-valid incident before a later ATC approval. The
    current orchestrator does not perform that reconnect handoff.

    Consumed commands are retained as normalized JSON for this reset lifecycle;
    the orchestrator separately owns durable API idempotency. Command time must
    be at or after incident creation and its first accepted observation. Later
    redelivery does not move that threshold. No clock is supplied to decide(),
    so future dating and maximum age cannot be independently checked here.

    Evidence UUIDs are references, not independently verified evidence;
    v1 supplies neither fallback prerequisites nor recovery/failure callbacks.
    Guardian recovery cannot revoke the retained incident through this Protocol.
    The orchestrator must enforce current incident validity before calling decide.
    """

    _TRANSITIONS = {
        SentinelState.STANDBY: frozenset({SentinelState.STANDBY, SentinelState.AWAITING_ATC}),
        SentinelState.AWAITING_ATC: frozenset({SentinelState.STANDBY, SentinelState.SIM_ACTION_RUNNING}),
        SentinelState.SIM_ACTION_RUNNING: frozenset({SentinelState.COMPLETED}),
        SentinelState.COMPLETED: frozenset(),
        SentinelState.ABORTED: frozenset(),
        SentinelState.LOCAL_FALLBACK: frozenset(),
    }

    def __init__(self) -> None:
        self._state = SentinelState.STANDBY
        self._run_id: UUID | None = None
        self._atc_connected = True
        self._incident: GuardianIncident | None = None
        self._pending: SentinelDecision | None = None
        self._authorization: SentinelDecision | None = None
        self._incident_observed_at: datetime | None = None
        self._consumed_commands: dict[UUID, str] = {}

    @property
    def state(self) -> SentinelState:
        return self._state

    def _transition(self, target: SentinelState) -> None:
        if target not in self._TRANSITIONS[self._state]:
            raise ValueError(f"invalid Sentinel transition: {self._state.value} -> {target.value}")
        self._state = target

    def _require_run(self, scenario_run_id: UUID) -> None:
        if self._run_id is None or scenario_run_id != self._run_id:
            raise ValueError("Sentinel rejected invalid or stale scenario_run_id")

    def reset(self, scenario_run_id: UUID, atc_connected: bool) -> None:
        if not isinstance(scenario_run_id, UUID):
            raise ValueError("scenario_run_id must be a UUID")
        if type(atc_connected) is not bool:
            raise ValueError("atc_connected must be a bool")
        # Reset is the sole operation allowed to reopen a terminal lifecycle.
        self._run_id = scenario_run_id
        self._atc_connected = atc_connected
        self._incident = None
        self._pending = None
        self._authorization = None
        self._incident_observed_at = None
        self._consumed_commands.clear()
        self._state = SentinelState.STANDBY

    def on_incident(self, incident: GuardianIncident, observed_at: datetime) -> SentinelDecision:
        if not isinstance(incident, GuardianIncident):
            raise ValueError("Sentinel requires a canonical GuardianIncident")
        # Revalidate mutable models and detach nested evidence lists from callers.
        candidate = GuardianIncident.model_validate(incident.model_dump())
        self._require_run(candidate.scenario_run_id)
        if candidate.guardian_state != GuardianState.ESCALATED:
            raise ValueError("Sentinel requires an ESCALATED Guardian incident")
        if candidate.incident_type != IncidentType.DUAL_PILOT_UNRESPONSIVE:
            raise ValueError("Sentinel requires a DUAL_PILOT_UNRESPONSIVE incident")
        if self._state not in {SentinelState.STANDBY, SentinelState.AWAITING_ATC}:
            raise ValueError("incident delivery cannot reopen a running or terminal lifecycle")
        if self._incident is not None and candidate != self._incident:
            raise ValueError("Sentinel rejected conflicting active incident replacement")
        if not isinstance(observed_at, datetime) or observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("observed_at must be a timezone-aware datetime")
        observed_at = observed_at.astimezone(timezone.utc)
        if observed_at < candidate.created_at:
            raise ValueError("incident observation cannot precede incident creation")
        if self._pending is not None:
            return self._pending.model_copy(deep=True)

        target = SentinelState.AWAITING_ATC if self._atc_connected else SentinelState.STANDBY
        # Construct and validate the output before making any state changes.
        pending = SentinelDecision(
            decision_id=uuid4(),
            scenario_run_id=candidate.scenario_run_id,
            incident_id=candidate.incident_id,
            sentinel_state=target,
            action_type=SimulatorActionType.NO_OP,
            authorization_source=AuthorizationSource.NONE,
            reason=(
                "Waiting for explicit matching simulated ATC approval."
                if self._atc_connected
                else "ATC link is disconnected; v1 inputs do not establish fallback authorization."
            ),
            evidence_event_ids=candidate.evidence_event_ids,
            executed_at=observed_at,
            result=DecisionResult.PENDING,
        )
        self._transition(target)
        self._incident = candidate
        if self._incident_observed_at is None:
            self._incident_observed_at = observed_at
        self._pending = pending
        return pending.model_copy(deep=True)

    def decide(self, decision: ATCDecision) -> SentinelDecision:
        if not isinstance(decision, ATCDecision):
            raise ValueError("Sentinel requires a canonical ATCDecision")
        candidate = ATCDecision.model_validate(decision.model_dump())
        request_content = candidate.model_dump_json()
        # Integrity checks precede context checks so changed run/incident fields
        # under an already consumed ID are reported as identity conflicts too.
        consumed = self._consumed_commands.get(candidate.command_id)
        if consumed is not None:
            if consumed != request_content:
                raise ValueError("Sentinel command_id conflict: consumed ID has different content")
            raise ValueError("Sentinel replayed command_id: already consumed; not awaiting another authorization")
        self._require_run(candidate.scenario_run_id)
        if self._incident is None:
            raise ValueError("Sentinel has no active incident")
        if candidate.incident_id != self._incident.incident_id:
            raise ValueError("Sentinel rejected mismatched incident_id")
        if not self._atc_connected or self._state != SentinelState.AWAITING_ATC:
            raise ValueError("Sentinel is not awaiting simulated ATC")
        approved = candidate.decision == ATCDecisionType.APPROVE
        if approved and candidate.requested_action == SimulatorActionType.NO_OP:
            raise ValueError("APPROVE must request a non-NO_OP symbolic action")
        if self._incident_observed_at is None:
            raise ValueError("Sentinel has no accepted incident observation time")
        if candidate.issued_at < self._incident.created_at:
            raise ValueError("ATC decision cannot precede incident creation")
        if candidate.issued_at < self._incident_observed_at:
            raise ValueError("ATC decision cannot precede first accepted incident observation")
        result = SentinelDecision(
            decision_id=uuid4(),
            scenario_run_id=candidate.scenario_run_id,
            incident_id=candidate.incident_id,
            sentinel_state=SentinelState.SIM_ACTION_RUNNING if approved else self._state,
            action_type=candidate.requested_action if approved else SimulatorActionType.NO_OP,
            authorization_source=AuthorizationSource.SIMULATED_ATC,
            reason=(
                "Unused simulated ATC APPROVE matched the active run, incident and event-time ordering."
                if approved
                else "Simulated ATC rejected the requested action; no action authorized."
            ),
            evidence_event_ids=self._incident.evidence_event_ids,
            executed_at=candidate.issued_at,
            result=DecisionResult.APPROVED if approved else DecisionResult.REJECTED,
        )
        # Prepare all copies before committing bookkeeping or lifecycle changes.
        authorization = result.model_copy(deep=True) if approved else None
        if approved:
            self._transition(SentinelState.SIM_ACTION_RUNNING)
            self._authorization = authorization
            self._pending = None
        self._consumed_commands[candidate.command_id] = request_content
        return result

    def set_atc_link(self, scenario_run_id: UUID, connected: bool) -> None:
        if type(connected) is not bool:
            raise ValueError("connected must be a bool")
        self._require_run(scenario_run_id)
        if connected == self._atc_connected:
            return
        if not connected and self._state == SentinelState.AWAITING_ATC:
            self._transition(SentinelState.STANDBY)
        self._atc_connected = connected
        self._pending = None

    def complete_action(self) -> None:
        """Record the orchestrator's completion notification without executing.

        The parameterless v1 callback cannot correlate a delayed notification to
        a run/action or distinguish simulator success from failure. In particular,
        an old callback arriving while a new run is running cannot be identified.
        Only the orchestrator can supply that ordering/outcome guarantee today.
        """
        if self._state != SentinelState.SIM_ACTION_RUNNING:
            raise ValueError("no simulator action is running")
        self._transition(SentinelState.COMPLETED)
