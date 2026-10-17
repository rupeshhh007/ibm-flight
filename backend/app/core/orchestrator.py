from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel

from app.contracts.enums import (
    ATCDecisionType,
    AuthorizationSource,
    DecisionResult,
    EventSource,
    EventType,
    GuardianState,
    PilotId,
    SentinelState,
    SimulatorActionType,
)
from app.contracts.interfaces import (
    AircraftSimulator,
    EventPublisher,
    EventStore,
    GuardianAgent,
    SentinelAgent,
    VisionAdapter,
)
from app.contracts.models import (
    ATCDecision,
    ATCLinkChangedPayload,
    CommandRecord,
    CommandResponse,
    CommunicationLinkRequest,
    CommunicationStatus,
    DomainEvent,
    EventHistoryResponse,
    GuardianIncident,
    IncidentListResponse,
    PilotAcknowledgement,
    PilotSnapshot,
    ScenarioAdvancedPayload,
    ScenarioAdvanceRequest,
    ScenarioListResponse,
    ScenarioResetPayload,
    ScenarioResetRequest,
    ScenarioStartRequest,
    ScenarioStartedPayload,
    SimulatorActionPayload,
    SentinelDecision,
    StoredEvent,
    SystemSnapshot,
)
from app.core.clock import VirtualClock
from app.scenarios.catalog import get_scenario, list_scenarios
from app.scenarios.runner import ScenarioRunner


logger = logging.getLogger(__name__)


class DomainError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class Orchestrator:
    def __init__(
        self,
        store: EventStore,
        publisher: EventPublisher,
        clock: VirtualClock,
        vision: VisionAdapter,
        simulator: AircraftSimulator,
        guardian: GuardianAgent,
        sentinel: SentinelAgent,
    ) -> None:
        self.store = store
        self.publisher = publisher
        self.clock = clock
        self.vision = vision
        self.simulator = simulator
        self.guardian = guardian
        self.sentinel = sentinel
        self._lock = threading.RLock()
        self._runner: ScenarioRunner | None = None
        self._incidents: list[GuardianIncident] = []
        # Tracks incidents actually delivered to Sentinel in this run. A Guardian
        # recovery must invalidate this grant even if Sentinel lacks revocation.
        self._sentinel_admitted_incident_id: UUID | None = None
        now = self.clock.now()
        self._snapshot = SystemSnapshot(
            pilots=[PilotSnapshot(pilot_id=PilotId.PILOT_1), PilotSnapshot(pilot_id=PilotId.PILOT_2)],
            communication=CommunicationStatus(atc_link_connected=True, last_change_at=now),
            latest_event_seq=self.store.latest_seq(),
        )

    @property
    def snapshot(self) -> SystemSnapshot:
        return self._snapshot.model_copy(deep=True)

    def scenarios(self) -> ScenarioListResponse:
        return ScenarioListResponse(scenarios=list_scenarios())

    @staticmethod
    def _fingerprint(request: BaseModel) -> str:
        body = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def _existing(self, command_id: UUID, fingerprint: str) -> CommandResponse | None:
        record = self.store.get_command(command_id)
        if record is None:
            return None
        if record.fingerprint != fingerprint:
            raise DomainError("COMMAND_ID_CONFLICT", "command_id was already used with a different request")
        prior = CommandResponse.model_validate_json(record.result_json)
        return prior.model_copy(update={"duplicate": True, "message": f"Duplicate command: {prior.message}"})

    def _reject_unrecorded_atc_replay(self, request: ATCDecision, fingerprint: str) -> None:
        """Fail closed on a durable ATC intent lacking a cached command result.

        The existing EventStore Protocol exposes only paginated replay, not an
        atomic command/outcome transaction. Never repeat a symbolic side effect
        solely because record_command or the later audit append failed.
        """
        after_seq = 0
        while True:
            batch = self.store.read_after(after_seq, 500)
            if not batch:
                return
            for event in batch:
                if event.event_type != EventType.ATC_DECISION:
                    continue
                prior = event.payload
                if not isinstance(prior, ATCDecision) or prior.command_id != request.command_id:
                    continue
                if self._fingerprint(prior) != fingerprint:
                    raise DomainError(
                        "COMMAND_ID_CONFLICT",
                        "command_id was already used with a different ATC request",
                    )
                raise DomainError(
                    "COMMAND_OUTCOME_UNCERTAIN",
                    "ATC command was durably received but its cached result is missing; "
                    "do not retry this action until the audit has been reconciled",
                )
            after_seq = batch[-1].seq
            if len(batch) < 500:
                return

    def _record(self, request: BaseModel, response: CommandResponse) -> None:
        self.store.record_command(
            CommandRecord(
                command_id=request.command_id,
                fingerprint=self._fingerprint(request),
                result_json=response.model_dump_json(),
            )
        )

    def _require_active(self, scenario_run_id: UUID) -> None:
        if self._snapshot.scenario_run_id is None:
            raise DomainError("NO_ACTIVE_SCENARIO", "no scenario is active")
        if scenario_run_id != self._snapshot.scenario_run_id:
            raise DomainError("STALE_SCENARIO_RUN", "scenario_run_id does not match the active run")

    def _refresh_guardian_snapshot(self) -> None:
        """Mirror Guardian's authoritative state; never retain a retired alert."""
        incident = self.guardian.active_incident
        self._snapshot.guardian_state = self.guardian.state
        self._snapshot.active_incident = incident.model_copy(deep=True) if incident else None
        if incident is None or incident.incident_id != self._sentinel_admitted_incident_id:
            self._sentinel_admitted_incident_id = None

    def _require_delivered_active_incident(self) -> GuardianIncident:
        """Only a still-escalated, already-handed-off incident may reach Sentinel."""
        cached = self._snapshot.active_incident
        active = self.guardian.active_incident
        if active is None or self.guardian.state != GuardianState.ESCALATED:
            self._refresh_guardian_snapshot()
            raise DomainError("NO_ACTIVE_INCIDENT", "no active Guardian incident can authorize this command")
        if (
            cached is None
            or cached != active
            or self._sentinel_admitted_incident_id != active.incident_id
        ):
            self._refresh_guardian_snapshot()
            raise DomainError(
                "INCIDENT_NOT_SYNCHRONIZED",
                "Guardian incident does not match the active Sentinel handoff",
            )
        return active

    def _event(
        self,
        event_type: EventType,
        source: EventSource,
        scenario_run_id: UUID,
        correlation_id: UUID,
        payload: BaseModel,
        causation_event_id: UUID | None = None,
        *,
        occurred_at: datetime | None = None,
    ) -> DomainEvent:
        return DomainEvent(
            event_id=uuid4(),
            event_type=event_type,
            occurred_at=(occurred_at if occurred_at is not None else self.clock.now()).astimezone(timezone.utc),
            source=source,
            scenario_run_id=scenario_run_id,
            correlation_id=correlation_id,
            causation_event_id=causation_event_id,
            payload=payload,
        )

    def _commit(self, events: list[DomainEvent]) -> list[StoredEvent]:
        stored = self.store.append(events)
        if stored:
            self._snapshot.latest_event_seq = stored[-1].seq
            self.publisher.publish(stored)
        return stored

    def start(self, request: ScenarioStartRequest) -> CommandResponse:
        with self._lock:
            fingerprint = self._fingerprint(request)
            if existing := self._existing(request.command_id, fingerprint):
                return existing
            try:
                definition = get_scenario(request.scenario_id)
            except ValueError as exc:
                raise DomainError("UNKNOWN_SCENARIO", str(exc), 404) from exc
            run_id = uuid4()
            now = self.clock.reset()
            self._runner = ScenarioRunner(definition)
            self.vision.configure_scenario(request.scenario_id)
            telemetry = self.simulator.start(run_id, request.scenario_id, now)
            self.guardian.reset(run_id)
            self.sentinel.reset(run_id, definition.atc_connected)
            self._sentinel_admitted_incident_id = None
            self._snapshot = SystemSnapshot(
                scenario_id=request.scenario_id,
                scenario_run_id=run_id,
                virtual_time=now,
                pilots=[PilotSnapshot(pilot_id=PilotId.PILOT_1), PilotSnapshot(pilot_id=PilotId.PILOT_2)],
                telemetry=telemetry,
                communication=CommunicationStatus(
                    atc_link_connected=definition.atc_connected,
                    last_change_at=now,
                ),
                latest_event_seq=self.store.latest_seq(),
            )
            stored = self._commit(
                [
                    self._event(
                        EventType.SCENARIO_STARTED,
                        EventSource.SCENARIO,
                        run_id,
                        request.command_id,
                        ScenarioStartedPayload(scenario_id=request.scenario_id, started_at=now),
                    ),
                    self._event(
                        EventType.TELEMETRY_UPDATED,
                        EventSource.SIMULATOR,
                        run_id,
                        request.command_id,
                        telemetry,
                    ),
                ]
            )
            response = CommandResponse(
                command_id=request.command_id,
                accepted=True,
                message=f"Started {request.scenario_id}",
                snapshot=self.snapshot,
                events=stored,
            )
            self._record(request, response)
            return response

    def advance(self, request: ScenarioAdvanceRequest) -> CommandResponse:
        with self._lock:
            self._require_active(request.scenario_run_id)
            fingerprint = self._fingerprint(request)
            if existing := self._existing(request.command_id, fingerprint):
                return existing
            if self._runner is None:
                raise DomainError("NO_SCENARIO_RUNNER", "active scenario runner is unavailable", 500)
            now = self.clock.advance(request.delta_ms)
            due_pilots = self._runner.advance(request.delta_ms)
            end_elapsed_ms = self._runner.elapsed_ms
            begin_elapsed_ms = end_elapsed_ms - request.delta_ms

            # ScenarioRunner currently returns pilot IDs without their scheduled
            # offsets. Resolve offsets from its own immutable scenario definition;
            # never stamp a due observation with the batch's final clock time.
            # Keep this adapter inside platform until Rohan adds an owned timed
            # runner API. No public contract or scenario code is changed here.
            due_times: dict[PilotId, deque[datetime]] = defaultdict(deque)
            for scheduled_ms, pilot_id in sorted(
                self._runner.definition.observation_schedule, key=lambda entry: entry[0]
            ):
                if begin_elapsed_ms < scheduled_ms <= end_elapsed_ms:
                    due_times[pilot_id].append(
                        now - timedelta(milliseconds=end_elapsed_ms - scheduled_ms)
                    )
            scheduled_observations: list[tuple[datetime, PilotId]] = []
            for pilot_id in due_pilots:
                # An injected test runner may supply unscheduled observations.
                # Preserve its old virtual-now behavior without changing the
                # production runner's existing public return type.
                timestamps = due_times[pilot_id]
                observed_at = timestamps.popleft() if timestamps else now
                scheduled_observations.append((observed_at, pilot_id))
            scheduled_observations.sort(key=lambda entry: entry[0])

            telemetry = self.simulator.advance(request.scenario_run_id, now)
            base_events: list[DomainEvent] = [
                self._event(
                    EventType.SCENARIO_ADVANCED,
                    EventSource.SCENARIO,
                    request.scenario_run_id,
                    request.command_id,
                    ScenarioAdvancedPayload(delta_ms=request.delta_ms, virtual_time=now),
                ),
                self._event(
                    EventType.TELEMETRY_UPDATED,
                    EventSource.SIMULATOR,
                    request.scenario_run_id,
                    request.command_id,
                    telemetry,
                ),
            ]
            observations = []
            for observed_at, pilot_id in scheduled_observations:
                observation = self.vision.observe(pilot_id, observed_at)
                observations.append(observation)
                base_events.append(
                    self._event(
                        EventType.PILOT_OBSERVATION,
                        EventSource.VISION,
                        request.scenario_run_id,
                        request.command_id,
                        observation,
                        occurred_at=observed_at,
                    )
                )
            committed = self._commit(base_events)
            by_pilot = {item.pilot_id: item for item in self._snapshot.pilots}
            for observation in observations:
                by_pilot[observation.pilot_id].latest_observation = observation
            self._snapshot.telemetry = telemetry
            self._snapshot.virtual_time = now
            derived: list[StoredEvent] = []
            for event in committed:
                if event.event_type != EventType.PILOT_OBSERVATION:
                    continue
                incident = self.guardian.consume_observation(event)
                if incident is not None and self._snapshot.active_incident is None:
                    incident_event = self._event(
                        EventType.GUARDIAN_INCIDENT,
                        EventSource.GUARDIAN,
                        request.scenario_run_id,
                        request.command_id,
                        incident,
                        event.event_id,
                        occurred_at=event.occurred_at,
                    )
                    incident_stored = self._commit([incident_event])
                    derived.extend(incident_stored)
                    self._incidents.append(incident)
                    self._snapshot.active_incident = incident
                    sentinel_decision = self.sentinel.on_incident(incident, event.occurred_at)
                    self._sentinel_admitted_incident_id = incident.incident_id
                    derived.extend(
                        self._commit(
                            [
                                self._event(
                                    EventType.SENTINEL_DECISION,
                                    EventSource.SENTINEL,
                                    request.scenario_run_id,
                                    request.command_id,
                                    sentinel_decision,
                                    incident_stored[-1].event_id,
                                    occurred_at=event.occurred_at,
                                )
                            ]
                        )
                    )
            # A later credible responsive observation may retire an earlier incident
            # without emitting a new GuardianIncident. Never leave its snapshot live.
            self._refresh_guardian_snapshot()
            self._snapshot.sentinel_state = self.sentinel.state
            response = CommandResponse(
                command_id=request.command_id,
                accepted=True,
                message=f"Advanced virtual time by {request.delta_ms} ms",
                snapshot=self.snapshot,
                events=committed + derived,
            )
            self._record(request, response)
            return response

    def acknowledge(self, acknowledgement: PilotAcknowledgement) -> CommandResponse:
        with self._lock:
            self._require_active(acknowledgement.scenario_run_id)
            fingerprint = self._fingerprint(acknowledgement)
            if existing := self._existing(acknowledgement.command_id, fingerprint):
                return existing
            active_incident = self._require_delivered_active_incident()
            if acknowledgement.alert_id != active_incident.incident_id:
                raise DomainError("INCIDENT_MISMATCH", "alert_id does not match the active incident")
            self.guardian.acknowledge(acknowledgement)
            stored = self._commit(
                [
                    self._event(
                        EventType.PILOT_ACKNOWLEDGED,
                        EventSource.PILOT,
                        acknowledgement.scenario_run_id,
                        acknowledgement.command_id,
                        acknowledgement,
                    )
                ]
            )
            self._refresh_guardian_snapshot()
            response = CommandResponse(
                command_id=acknowledgement.command_id,
                accepted=True,
                message="Pilot acknowledgement accepted",
                snapshot=self.snapshot,
                events=stored,
            )
            self._record(acknowledgement, response)
            return response

    def atc_decision(self, decision: ATCDecision) -> CommandResponse:
        with self._lock:
            self._require_active(decision.scenario_run_id)
            fingerprint = self._fingerprint(decision)
            if existing := self._existing(decision.command_id, fingerprint):
                return existing
            # The write-ahead ATC intent is authoritative even when final response
            # caching fails. Prevent replay across storage/HTTP error boundaries.
            self._reject_unrecorded_atc_replay(decision, fingerprint)
            # Guardian, not a possibly stale snapshot or Sentinel's retained state,
            # is the current incident authority. This gate MUST precede decide().
            active_incident = self._require_delivered_active_incident()
            if decision.incident_id != active_incident.incident_id:
                raise DomainError("INCIDENT_MISMATCH", "incident_id does not match the active incident")
            try:
                sentinel_decision = self.sentinel.decide(decision)
            except ValueError as exc:
                raise DomainError("AUTHORIZATION_REJECTED", str(exc)) from exc
            domain_events = [
                self._event(
                    EventType.ATC_DECISION,
                    EventSource.SIMULATED_ATC,
                    decision.scenario_run_id,
                    decision.command_id,
                    decision,
                ),
                self._event(
                    EventType.SENTINEL_DECISION,
                    EventSource.SENTINEL,
                    decision.scenario_run_id,
                    decision.command_id,
                    sentinel_decision,
                ),
            ]
            message = "Simulated ATC rejection recorded; no action executed"
            accepted = True
            intent_stored: list[StoredEvent] = []
            if decision.decision == ATCDecisionType.APPROVE:
                # Simulator execution is a separate trust boundary. A positive ATC
                # decision is NOT proof that the simulator executed successfully.
                if (
                    sentinel_decision.scenario_run_id != decision.scenario_run_id
                    or sentinel_decision.incident_id != decision.incident_id
                    or sentinel_decision.action_type != decision.requested_action
                    or sentinel_decision.authorization_source != AuthorizationSource.SIMULATED_ATC
                    or sentinel_decision.result != DecisionResult.APPROVED
                    or sentinel_decision.sentinel_state != SentinelState.SIM_ACTION_RUNNING
                ):
                    raise DomainError(
                        "AUTHORIZATION_REJECTED",
                        "Sentinel did not issue a matching, approved simulated-action authorization",
                    )

                # Durable authorization intent MUST precede the external simulator
                # side effect. If storage or event publication fails here, do not
                # invoke the simulator; the retained Sentinel state fails closed.
                try:
                    intent_stored = self._commit(domain_events)
                    if len(intent_stored) != len(domain_events):
                        raise RuntimeError("ATC intent append did not acknowledge all events")
                except Exception as exc:
                    logger.exception("ATC intent persistence failed; simulator was not invoked")
                    raise DomainError(
                        "ATC_INTENT_UNAVAILABLE",
                        "Could not record ATC authorization intent; no simulator action was attempted",
                        503,
                    ) from exc
                domain_events = []

                action: SimulatorActionPayload | None = None
                failure_reason: str | None = None
                executed = False
                try:
                    candidate = self.simulator.apply_action(
                        decision.scenario_run_id,
                        decision.requested_action,
                        sentinel_decision,
                        self.clock.now(),
                    )
                except Exception:
                    logger.exception("Simulator raised during a symbolic action attempt")
                    failure_reason = "Simulator raised an error; execution outcome is unconfirmed"
                else:
                    # Revalidate mutable Pydantic models rather than trusting an
                    # adapter's `model_copy(update=...)` or accidental wrong-run reply.
                    try:
                        if not isinstance(candidate, SimulatorActionPayload):
                            raise ValueError("simulator returned a non-canonical action payload")
                        candidate = SimulatorActionPayload.model_validate(candidate.model_dump())
                    except Exception:
                        failure_reason = "Simulator returned an invalid action payload; execution unconfirmed"
                    else:
                        if (
                            candidate.scenario_run_id != decision.scenario_run_id
                            or candidate.action_type != decision.requested_action
                            or candidate.authorization_source != AuthorizationSource.SIMULATED_ATC
                        ):
                            failure_reason = "Simulator action context mismatch; execution unconfirmed"
                        elif not candidate.authorized or candidate.result != DecisionResult.EXECUTED:
                            failure_reason = "Simulator did not confirm authorized execution"
                        else:
                            action = candidate

                if action is not None:
                    # Record the actual successful action even if the subsequent
                    # parameterless Sentinel completion callback should fail.
                    domain_events.append(
                        self._event(
                            EventType.SIMULATOR_ACTION,
                            EventSource.SIMULATOR,
                            decision.scenario_run_id,
                            decision.command_id,
                            action,
                        )
                    )
                    executed = True
                    self._snapshot.last_simulator_action = action
                    try:
                        self.sentinel.complete_action()
                    except Exception:
                        logger.exception("Sentinel completion failed after verified simulator action")
                        failure_reason = "Simulator action executed, but Sentinel completion failed"
                    else:
                        completion = SentinelDecision(
                            decision_id=uuid4(),
                            scenario_run_id=decision.scenario_run_id,
                            incident_id=decision.incident_id,
                            sentinel_state=SentinelState.COMPLETED,
                            action_type=decision.requested_action,
                            authorization_source=AuthorizationSource.SIMULATED_ATC,
                            reason="Simulator independently validated and executed one symbolic action.",
                            evidence_event_ids=active_incident.evidence_event_ids,
                            executed_at=self.clock.now(),
                            result=DecisionResult.EXECUTED,
                        )
                        domain_events.append(
                            self._event(
                                EventType.SENTINEL_DECISION,
                                EventSource.SENTINEL,
                                decision.scenario_run_id,
                                decision.command_id,
                                completion,
                            )
                        )
                        message = f"Executed one authorized symbolic action: {decision.requested_action.value}"

                if failure_reason is not None:
                    # The v1 Sentinel Protocol has no abort/failure transition.
                    # Remain fail-closed in SIM_ACTION_RUNNING; never invent a
                    # COMPLETED / EXECUTED decision for a failed or unknown result.
                    failure = SentinelDecision(
                        decision_id=uuid4(),
                        scenario_run_id=decision.scenario_run_id,
                        incident_id=decision.incident_id,
                        sentinel_state=self.sentinel.state,
                        action_type=decision.requested_action,
                        authorization_source=AuthorizationSource.SIMULATED_ATC,
                        reason=(
                            f"{failure_reason}; reconcile or reset the scenario before a new attempt."
                        ),
                        evidence_event_ids=active_incident.evidence_event_ids,
                        executed_at=self.clock.now(),
                        result=DecisionResult.FAILED,
                    )
                    domain_events.append(
                        self._event(
                            EventType.SENTINEL_DECISION,
                            EventSource.SENTINEL,
                            decision.scenario_run_id,
                            decision.command_id,
                            failure,
                        )
                    )
                    accepted = False
                    message = (
                        f"{failure_reason}; verified action recorded, but completion requires reconciliation"
                        if executed
                        else f"{failure_reason}; no successful execution recorded; reset/reconcile before retry"
                    )
            # A simulator action can have executed even if the final append
            # fails. Never retry an already-journaled ATC intent automatically.
            try:
                result_stored = self._commit(domain_events)
            except Exception as exc:
                self._snapshot.sentinel_state = self.sentinel.state
                logger.exception("ATC result persistence failed; outcome may have side effects")
                raise DomainError(
                    "ATC_OUTCOME_UNCERTAIN",
                    "Action outcome could not be durably recorded; do not retry or "
                    "treat it as completed until the audit is reconciled",
                    503,
                ) from exc
            stored = intent_stored + result_stored
            self._snapshot.sentinel_state = self.sentinel.state
            response = CommandResponse(
                command_id=decision.command_id,
                accepted=accepted,
                message=message,
                snapshot=self.snapshot,
                events=stored,
            )
            try:
                self._record(decision, response)
            except Exception as exc:
                logger.exception("ATC command-result caching failed after event persistence")
                raise DomainError(
                    "ATC_RESULT_CACHE_UNAVAILABLE",
                    "ATC events were journaled but the command result is not cached; "
                    "inspect the audit before attempting another command",
                    503,
                ) from exc
            return response

    def set_link(self, request: CommunicationLinkRequest) -> CommandResponse:
        with self._lock:
            self._require_active(request.scenario_run_id)
            fingerprint = self._fingerprint(request)
            if existing := self._existing(request.command_id, fingerprint):
                return existing

            # Reconnect is only a delivery opportunity, never an authorization.
            # Preserve proof that the incident was already admitted to Sentinel
            # before refreshing the (possibly stale) platform snapshot.
            was_connected = self._snapshot.communication.atc_link_connected
            guardian_incident = self.guardian.active_incident
            replay_incident = (
                guardian_incident
                if request.atc_link_connected
                and not was_connected
                and self.sentinel.state == SentinelState.STANDBY
                and self.guardian.state == GuardianState.ESCALATED
                and guardian_incident is not None
                and self._snapshot.active_incident == guardian_incident
                and self._sentinel_admitted_incident_id == guardian_incident.incident_id
                else None
            )

            self.sentinel.set_atc_link(request.scenario_run_id, request.atc_link_connected)
            payload = ATCLinkChangedPayload(
                command_id=request.command_id,
                atc_link_connected=request.atc_link_connected,
                changed_at=request.changed_at,
            )
            stored = self._commit(
                [
                    self._event(
                        EventType.ATC_LINK_CHANGED,
                        EventSource.SYSTEM,
                        request.scenario_run_id,
                        request.command_id,
                        payload,
                    )
                ]
            )
            self._snapshot.communication = self._snapshot.communication.model_copy(
                update={"atc_link_connected": request.atc_link_connected, "last_change_at": request.changed_at}
            )
            # A retired incident must stay retired even if Sentinel still holds
            # its old local incident. No stale/unsynchronized episode is replayed.
            self._refresh_guardian_snapshot()
            redelivery_rejected = False
            if replay_incident is not None:
                # Re-deliver the *same* authorized handoff as a new pending
                # decision. The frozen Sentinel Protocol intentionally has no
                # direct reconnect-resume method; on_incident is its safe gate.
                try:
                    pending = self.sentinel.on_incident(replay_incident, self.clock.now())
                except ValueError:
                    # The link change is already durable. Record its command
                    # result rather than failing the request after a side effect.
                    # The invariant remains fail-closed: no handoff, no approval.
                    redelivery_rejected = True
                else:
                    stored.extend(self._commit([
                        self._event(
                            EventType.SENTINEL_DECISION,
                            EventSource.SENTINEL,
                            request.scenario_run_id,
                            request.command_id,
                            pending,
                            stored[0].event_id,
                        )
                    ]))
            self._snapshot.sentinel_state = self.sentinel.state
            response = CommandResponse(
                command_id=request.command_id,
                accepted=True,
                message=(
                    "Simulated ATC link updated; incident redelivery rejected; no action authorized"
                    if redelivery_rejected
                    else "Simulated ATC link updated; link state alone authorizes no action"
                ),
                snapshot=self.snapshot,
                events=stored,
            )
            self._record(request, response)
            return response

    def reset(self, request: ScenarioResetRequest) -> CommandResponse:
        with self._lock:
            fingerprint = self._fingerprint(request)
            if existing := self._existing(request.command_id, fingerprint):
                return existing
            self._require_active(request.scenario_run_id)
            if self._snapshot.scenario_id is None:
                raise DomainError("NO_ACTIVE_SCENARIO", "no scenario is active")
            scenario_id = self._snapshot.scenario_id
            definition = get_scenario(scenario_id)
            new_run_id = uuid4()
            now = self.clock.reset()
            self._runner = ScenarioRunner(definition)
            self.vision.configure_scenario(scenario_id)
            telemetry = self.simulator.reset(new_run_id, scenario_id, now)
            self.guardian.reset(new_run_id)
            self.sentinel.reset(new_run_id, definition.atc_connected)
            self._sentinel_admitted_incident_id = None
            self._snapshot = SystemSnapshot(
                scenario_id=scenario_id,
                scenario_run_id=new_run_id,
                virtual_time=now,
                pilots=[PilotSnapshot(pilot_id=PilotId.PILOT_1), PilotSnapshot(pilot_id=PilotId.PILOT_2)],
                telemetry=telemetry,
                communication=CommunicationStatus(
                    atc_link_connected=definition.atc_connected,
                    last_change_at=now,
                ),
                latest_event_seq=self.store.latest_seq(),
            )
            stored = self._commit(
                [
                    self._event(
                        EventType.SCENARIO_RESET,
                        EventSource.SCENARIO,
                        new_run_id,
                        request.command_id,
                        ScenarioResetPayload(
                            command_id=request.command_id,
                            previous_scenario_run_id=request.scenario_run_id,
                            new_scenario_run_id=new_run_id,
                            reset_at=now,
                        ),
                    ),
                    self._event(
                        EventType.TELEMETRY_UPDATED,
                        EventSource.SIMULATOR,
                        new_run_id,
                        request.command_id,
                        telemetry,
                    ),
                ]
            )
            response = CommandResponse(
                command_id=request.command_id,
                accepted=True,
                message="Scenario reset with a new run identity; prior audit history retained",
                snapshot=self.snapshot,
                events=stored,
            )
            self._record(request, response)
            return response

    def history(self, after_seq: int, limit: int) -> EventHistoryResponse:
        events = self.store.read_after(after_seq, limit)
        return EventHistoryResponse(
            events=events,
            after_seq=after_seq,
            limit=limit,
            latest_event_seq=self.store.latest_seq(),
        )

    def incidents(self) -> IncidentListResponse:
        return IncidentListResponse(incidents=list(self._incidents))

    def close(self) -> None:
        self.store.close()
