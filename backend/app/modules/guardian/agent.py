from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid5

from app.contracts.enums import (
    EventType,
    GuardianState,
    IncidentSeverity,
    IncidentType,
    PilotId,
    PilotObservationStatus,
)
from app.contracts.models import GuardianIncident, PilotAcknowledgement, PilotObservation, StoredEvent

from .policy import GuardianPolicy


class GuardianReason(StrEnum):
    RESET = "RESET"
    FIRST_CREDIBLE_CONCERN = "FIRST_CREDIBLE_CONCERN"
    REPEATED_CREDIBLE_CONCERN = "REPEATED_CREDIBLE_CONCERN"
    DUAL_FRESH_EVIDENCE = "DUAL_FRESH_EVIDENCE"
    CONCERN_RESOLVING = "CONCERN_RESOLVING"
    RECOVERY_COMPLETE = "RECOVERY_COMPLETE"
    NEW_CONCERN_DURING_RECOVERY = "NEW_CONCERN_DURING_RECOVERY"
    EVIDENCE_EXPIRED = "EVIDENCE_EXPIRED"
    ACKNOWLEDGED = "ACKNOWLEDGED"


@dataclass(frozen=True)
class _Evidence:
    event_id: UUID
    seq: int
    observed_at: datetime


@dataclass
class _PilotEvidence:
    concerns: deque[_Evidence] = field(default_factory=deque)
    last_observed_at: datetime | None = None
    last_event_seq: int | None = None
    latest_status: PilotObservationStatus | None = None
    latest_usable: bool = False
    latest_responsive_at: datetime | None = None
    unknown_streak: int = 0
    recovery_responses: deque[datetime] = field(default_factory=deque)


_ALLOWED_TRANSITIONS: dict[GuardianState, set[GuardianState]] = {
    GuardianState.NORMAL: {GuardianState.SUSPECTED},
    GuardianState.SUSPECTED: {
        GuardianState.NORMAL,
        GuardianState.AWAITING_ACK,
        GuardianState.RECOVERING,
    },
    GuardianState.AWAITING_ACK: {
        GuardianState.NORMAL,
        GuardianState.SUSPECTED,
        GuardianState.ESCALATED,
        GuardianState.RECOVERING,
    },
    GuardianState.ESCALATED: {GuardianState.RECOVERING},
    GuardianState.RECOVERING: {
        GuardianState.NORMAL,
        GuardianState.SUSPECTED,
        GuardianState.AWAITING_ACK,
    },
}


class DeterministicGuardianAgent:
    """Conservative, observation-only Guardian implementation.

    The agent uses event time as its logical clock. Duplicate events are
    ignored; stale runs, malformed envelopes, and out-of-order inputs are
    rejected without mutating monitoring state.
    """

    def __init__(self, policy: GuardianPolicy | None = None) -> None:
        self.policy = policy or GuardianPolicy()
        self._state = GuardianState.NORMAL
        self._run_id: UUID | None = None
        self._active_incident: GuardianIncident | None = None
        self._pilots = {pilot_id: _PilotEvidence() for pilot_id in PilotId}
        self._processed_ids: deque[UUID] = deque()
        self._processed_id_set: set[UUID] = set()
        self._acknowledgement_ids: deque[UUID] = deque()
        self._acknowledgements: dict[UUID, PilotAcknowledgement] = {}
        self._last_seq: int | None = None
        self._last_event_time: datetime | None = None
        self._episode_started_at: datetime | None = None
        self._recovery_started_at: datetime | None = None
        self._last_transition_reason = GuardianReason.RESET

    @property
    def state(self) -> GuardianState:
        return self._state

    @property
    def active_incident(self) -> GuardianIncident | None:
        return self._active_incident

    @property
    def last_transition_reason(self) -> GuardianReason:
        return self._last_transition_reason

    @property
    def retained_event_count(self) -> int:
        return len(self._processed_ids)

    def reset(self, scenario_run_id: UUID) -> None:
        self._run_id = scenario_run_id
        self._state = GuardianState.NORMAL
        self._active_incident = None
        self._pilots = {pilot_id: _PilotEvidence() for pilot_id in PilotId}
        self._processed_ids.clear()
        self._processed_id_set.clear()
        self._acknowledgement_ids.clear()
        self._acknowledgements.clear()
        self._last_seq = None
        self._last_event_time = None
        self._episode_started_at = None
        self._recovery_started_at = None
        self._last_transition_reason = GuardianReason.RESET

    def consume_observation(self, event: StoredEvent) -> GuardianIncident | None:
        observation = self._validate_event(event)
        if event.event_id in self._processed_id_set:
            return None
        if self._last_seq is not None and event.seq <= self._last_seq:
            raise ValueError("Guardian rejected duplicate or out-of-order event sequence")
        if self._last_event_time is not None and event.occurred_at < self._last_event_time:
            raise ValueError("Guardian rejected out-of-order observation time")

        pilot = self._pilots[observation.pilot_id]
        if pilot.last_observed_at is not None and observation.observed_at < pilot.last_observed_at:
            raise ValueError("Guardian rejected older pilot observation")

        self._remember_event(event.event_id)
        self._last_seq = event.seq
        self._last_event_time = event.occurred_at
        self._prune_expired(event.occurred_at)

        usable = self._is_usable(observation)
        previous_status = pilot.latest_status
        pilot.last_observed_at = observation.observed_at
        pilot.last_event_seq = event.seq
        pilot.latest_status = observation.observation_status
        pilot.latest_usable = usable

        if not usable:
            pilot.unknown_streak += 1
            self._reconcile_non_escalated_state()
            return None

        pilot.unknown_streak = 0
        if observation.observation_status == PilotObservationStatus.RESPONSIVE:
            self._consume_responsive(pilot, previous_status, observation.observed_at)
            return None

        self._consume_concern(pilot, event)
        if self._active_incident is not None:
            return None
        if not self._can_escalate(event.occurred_at):
            self._reconcile_non_escalated_state()
            return None

        evidence = self._incident_evidence()
        incident_name = "guardian:" + ":".join(str(item.event_id) for item in evidence)
        incident = GuardianIncident(
            incident_id=uuid5(event.scenario_run_id, incident_name),
            scenario_run_id=event.scenario_run_id,
            incident_type=IncidentType.DUAL_PILOT_UNRESPONSIVE,
            severity=IncidentSeverity.CRITICAL,
            guardian_state=GuardianState.ESCALATED,
            evidence_event_ids=[item.event_id for item in evidence],
            explanation=(
                "Rule G-DET-1: both pilots have at least "
                f"{self.policy.concerns_required_per_pilot} distinct usable concern observations "
                f"(quality >= {_format_quality(self.policy.minimum_observation_quality)}, spacing >= "
                f"{self.policy.minimum_independent_spacing_ms} ms) within "
                f"{self.policy.evidence_window_ms} ms; no latest usable pilot observation is responsive, "
                f"and the {self.policy.acknowledgement_grace_ms} ms event-time grace elapsed."
            ),
            acknowledgement_required=True,
            created_at=event.occurred_at,
        )
        self._transition(GuardianState.ESCALATED, GuardianReason.DUAL_FRESH_EVIDENCE)
        self._active_incident = incident
        self._reset_recovery_evidence(event.occurred_at)
        return incident

    def acknowledge(self, acknowledgement: PilotAcknowledgement) -> None:
        if self._run_id is None or acknowledgement.scenario_run_id != self._run_id:
            raise ValueError("Guardian rejected stale scenario_run_id")
        previous = self._acknowledgements.get(acknowledgement.command_id)
        if previous is not None:
            if previous == acknowledgement:
                return
            raise ValueError("Guardian rejected conflicting acknowledgement command_id")
        if self._active_incident is None:
            raise ValueError("Guardian rejected acknowledgement with no active incident")
        if acknowledgement.alert_id != self._active_incident.incident_id:
            raise ValueError("Guardian rejected acknowledgement for a different incident")
        if self._last_event_time is not None and acknowledgement.acknowledged_at < self._last_event_time:
            raise ValueError("Guardian rejected acknowledgement older than current evidence")

        self._remember_acknowledgement(acknowledgement)
        self._active_incident = None
        self._clear_concerns()
        self._reset_recovery_evidence(acknowledgement.acknowledged_at)
        for pilot in self._pilots.values():
            # Recovery requires new post-acknowledgement evidence. Do not let
            # the pre-acknowledgement concern status restart recovery counters.
            pilot.latest_status = None
            pilot.latest_usable = False
        if self._state != GuardianState.NORMAL:
            self._transition(GuardianState.RECOVERING, GuardianReason.ACKNOWLEDGED)

    def _validate_event(self, event: StoredEvent) -> PilotObservation:
        if event.event_type != EventType.PILOT_OBSERVATION or not isinstance(event.payload, PilotObservation):
            raise ValueError("Guardian accepts only stored PILOT_OBSERVATION events")
        if self._run_id is None or event.scenario_run_id != self._run_id:
            raise ValueError("Guardian rejected stale scenario_run_id")
        if event.occurred_at != event.payload.observed_at:
            raise ValueError("Guardian requires matching event and observation times")
        return event.payload

    def _is_usable(self, observation: PilotObservation) -> bool:
        return (
            observation.camera_available
            and observation.face_visible
            and observation.observation_status != PilotObservationStatus.UNKNOWN
            and observation.observation_quality >= self.policy.minimum_observation_quality
        )

    def _consume_concern(self, pilot: _PilotEvidence, event: StoredEvent) -> None:
        if self._state == GuardianState.RECOVERING:
            self._reset_recovery_evidence(None)
            self._transition(GuardianState.SUSPECTED, GuardianReason.NEW_CONCERN_DURING_RECOVERY)
        elif self._state == GuardianState.ESCALATED:
            self._reset_recovery_evidence(event.occurred_at)
        last = pilot.concerns[-1] if pilot.concerns else None
        spacing = timedelta(milliseconds=self.policy.minimum_independent_spacing_ms)
        if last is None or event.occurred_at - last.observed_at >= spacing:
            pilot.concerns.append(_Evidence(event.event_id, event.seq, event.occurred_at))
            while len(pilot.concerns) > self.policy.max_evidence_per_pilot:
                pilot.concerns.popleft()
            if self._episode_started_at is None:
                self._episode_started_at = event.occurred_at

    def _consume_responsive(
        self,
        pilot: _PilotEvidence,
        previous_status: PilotObservationStatus | None,
        observed_at: datetime,
    ) -> None:
        had_concern = bool(pilot.concerns) or previous_status == PilotObservationStatus.POSSIBLY_UNRESPONSIVE
        pilot.concerns.clear()
        self._recompute_episode_start()
        pilot.latest_responsive_at = observed_at
        if self._state == GuardianState.ESCALATED:
            self._record_recovery_response(pilot, observed_at)
            if self._recovery_threshold_met():
                self._active_incident = None
                self._clear_concerns()
                self._transition(GuardianState.RECOVERING, GuardianReason.CONCERN_RESOLVING)
                self._reset_recovery_evidence(observed_at)
            return
        if had_concern and self._state != GuardianState.NORMAL:
            self._transition(GuardianState.RECOVERING, GuardianReason.CONCERN_RESOLVING)
            self._reset_recovery_evidence(observed_at)
            return
        if self._state == GuardianState.RECOVERING:
            self._record_recovery_response(pilot, observed_at)
            if self._recovery_threshold_met():
                self._transition(GuardianState.NORMAL, GuardianReason.RECOVERY_COMPLETE)
                self._clear_concerns()
                self._reset_recovery_evidence(None)
            return
        self._reconcile_non_escalated_state()

    def _prune_expired(self, now: datetime) -> None:
        cutoff = now - timedelta(milliseconds=self.policy.evidence_window_ms)
        for pilot in self._pilots.values():
            while pilot.concerns and pilot.concerns[0].observed_at < cutoff:
                pilot.concerns.popleft()
            while pilot.recovery_responses and pilot.recovery_responses[0] < cutoff:
                pilot.recovery_responses.popleft()
        self._recompute_episode_start()

    def _can_escalate(self, now: datetime) -> bool:
        if self._state == GuardianState.ESCALATED or self._episode_started_at is None:
            return False
        if now - self._episode_started_at < timedelta(milliseconds=self.policy.acknowledgement_grace_ms):
            return False
        for pilot in self._pilots.values():
            if len(pilot.concerns) < self.policy.concerns_required_per_pilot:
                return False
            if not pilot.latest_usable or pilot.latest_status != PilotObservationStatus.POSSIBLY_UNRESPONSIVE:
                return False
        return True

    def _incident_evidence(self) -> list[_Evidence]:
        evidence = [
            item
            for pilot in self._pilots.values()
            for item in list(pilot.concerns)[-self.policy.concerns_required_per_pilot :]
        ]
        return sorted(evidence, key=lambda item: (item.observed_at, item.seq))

    def _reconcile_non_escalated_state(self) -> None:
        if self._state in {GuardianState.ESCALATED, GuardianState.RECOVERING}:
            return
        counts = [len(pilot.concerns) for pilot in self._pilots.values()]
        if max(counts, default=0) == 0:
            if self._state != GuardianState.NORMAL:
                self._transition(GuardianState.NORMAL, GuardianReason.EVIDENCE_EXPIRED)
            self._episode_started_at = None
        elif max(counts) >= self.policy.awaiting_ack_concerns:
            if self._state != GuardianState.AWAITING_ACK:
                self._transition(GuardianState.AWAITING_ACK, GuardianReason.REPEATED_CREDIBLE_CONCERN)
        elif self._state != GuardianState.SUSPECTED:
            self._transition(GuardianState.SUSPECTED, GuardianReason.FIRST_CREDIBLE_CONCERN)

    def _transition(self, target: GuardianState, reason: GuardianReason) -> None:
        if target == self._state:
            self._last_transition_reason = reason
            return
        if target not in _ALLOWED_TRANSITIONS[self._state]:
            raise RuntimeError(f"invalid Guardian transition: {self._state} -> {target}")
        self._state = target
        self._last_transition_reason = reason

    def _clear_concerns(self) -> None:
        for pilot in self._pilots.values():
            pilot.concerns.clear()
        self._episode_started_at = None

    def _recompute_episode_start(self) -> None:
        remaining = [evidence.observed_at for pilot in self._pilots.values() for evidence in pilot.concerns]
        self._episode_started_at = min(remaining, default=None)

    def _reset_recovery_evidence(self, boundary: datetime | None) -> None:
        self._recovery_started_at = boundary
        for pilot in self._pilots.values():
            pilot.recovery_responses.clear()

    def _record_recovery_response(self, pilot: _PilotEvidence, observed_at: datetime) -> None:
        if self._recovery_started_at is None or observed_at <= self._recovery_started_at:
            return
        spacing = timedelta(milliseconds=self.policy.minimum_independent_spacing_ms)
        if pilot.recovery_responses and observed_at - pilot.recovery_responses[-1] < spacing:
            return
        pilot.recovery_responses.append(observed_at)
        while len(pilot.recovery_responses) > self.policy.recovery_observations_required_per_pilot:
            pilot.recovery_responses.popleft()

    def _recovery_threshold_met(self) -> bool:
        return all(
            pilot.latest_usable
            and pilot.latest_status == PilotObservationStatus.RESPONSIVE
            and len(pilot.recovery_responses) >= self.policy.recovery_observations_required_per_pilot
            for pilot in self._pilots.values()
        )

    def _remember_event(self, event_id: UUID) -> None:
        self._processed_ids.append(event_id)
        self._processed_id_set.add(event_id)
        while len(self._processed_ids) > self.policy.max_processed_events:
            self._processed_id_set.remove(self._processed_ids.popleft())

    def _remember_acknowledgement(self, acknowledgement: PilotAcknowledgement) -> None:
        command_id = acknowledgement.command_id
        self._acknowledgement_ids.append(command_id)
        self._acknowledgements[command_id] = acknowledgement
        while len(self._acknowledgement_ids) > self.policy.max_acknowledgements:
            self._acknowledgements.pop(self._acknowledgement_ids.popleft(), None)


def _format_quality(value: float) -> str:
    text = str(value)
    if "e" in text.lower():
        return text
    if "." not in text:
        return f"{text}.00"
    whole, fraction = text.split(".", maxsplit=1)
    return f"{whole}.{fraction.ljust(2, '0')}"
