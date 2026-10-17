from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.contracts.enums import (
    EventSource,
    EventType,
    GuardianState,
    IncidentSeverity,
    IncidentType,
    PilotId,
    PilotObservationStatus,
)
from app.contracts.interfaces import GuardianAgent
from app.contracts.models import PilotAcknowledgement, PilotObservation, StoredEvent
from app.modules.guardian import DeterministicGuardianAgent, GuardianPolicy


BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
RUN_ID = UUID("10000000-0000-4000-8000-000000000001")
OTHER_RUN_ID = UUID("20000000-0000-4000-8000-000000000002")


def observation_event(
    seq: int,
    pilot_id: PilotId,
    status: PilotObservationStatus,
    *,
    at_ms: int,
    quality: float = 0.95,
    camera_available: bool = True,
    face_visible: bool = True,
    eyes_closed: bool | None = None,
    run_id: UUID = RUN_ID,
    event_id: UUID | None = None,
) -> StoredEvent:
    observed_at = BASE_TIME + timedelta(milliseconds=at_ms)
    observation = PilotObservation(
        pilot_id=pilot_id,
        observed_at=observed_at,
        observation_status=status,
        camera_available=camera_available,
        face_visible=face_visible,
        eyes_closed=(status == PilotObservationStatus.POSSIBLY_UNRESPONSIVE)
        if eyes_closed is None
        else eyes_closed,
        observation_duration_ms=500,
        observation_quality=quality,
    )
    return StoredEvent(
        seq=seq,
        event_id=event_id or UUID(int=10_000 + seq),
        event_type=EventType.PILOT_OBSERVATION,
        occurred_at=observed_at,
        source=EventSource.VISION,
        scenario_run_id=run_id,
        correlation_id=UUID(int=20_000 + seq),
        payload=observation,
    )


def acknowledgement(
    alert_id: UUID,
    *,
    command_id: UUID = UUID("30000000-0000-4000-8000-000000000003"),
    run_id: UUID = RUN_ID,
) -> PilotAcknowledgement:
    return PilotAcknowledgement(
        command_id=command_id,
        scenario_run_id=run_id,
        pilot_id=PilotId.PILOT_1,
        alert_id=alert_id,
        acknowledged_at=BASE_TIME + timedelta(seconds=3),
    )


def new_agent(policy: GuardianPolicy | None = None) -> DeterministicGuardianAgent:
    agent = DeterministicGuardianAgent(policy)
    agent.reset(RUN_ID)
    return agent


def escalate(agent: DeterministicGuardianAgent, *, start_seq: int = 1):
    events = [
        observation_event(start_seq, PilotId.PILOT_1, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=0),
        observation_event(start_seq + 1, PilotId.PILOT_2, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=0),
        observation_event(start_seq + 2, PilotId.PILOT_1, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=1_000),
        observation_event(start_seq + 3, PilotId.PILOT_2, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=1_000),
    ]
    incident = None
    for event in events:
        incident = agent.consume_observation(event) or incident
    assert incident is not None
    return incident, events


def test_enhanced_agent_conforms_to_frozen_protocol_and_models_roundtrip() -> None:
    agent = new_agent()
    assert isinstance(agent, GuardianAgent)
    event = observation_event(1, PilotId.PILOT_1, PilotObservationStatus.RESPONSIVE, at_ms=0)
    assert StoredEvent.model_validate_json(event.model_dump_json()) == event
    assert agent.consume_observation(event) is None


def test_rejects_wrong_event_type_stale_run_and_mismatched_time() -> None:
    agent = new_agent()
    valid = observation_event(1, PilotId.PILOT_1, PilotObservationStatus.RESPONSIVE, at_ms=0)
    wrong_type = valid.model_copy(update={"event_type": EventType.TELEMETRY_UPDATED})
    with pytest.raises(ValueError, match="only stored PILOT_OBSERVATION"):
        agent.consume_observation(wrong_type)
    with pytest.raises(ValueError, match="stale scenario_run_id"):
        agent.consume_observation(
            observation_event(1, PilotId.PILOT_1, PilotObservationStatus.RESPONSIVE, at_ms=0, run_id=OTHER_RUN_ID)
        )
    mismatched_time = valid.model_copy(update={"occurred_at": BASE_TIME + timedelta(seconds=1)})
    with pytest.raises(ValueError, match="matching event and observation times"):
        agent.consume_observation(mismatched_time)


@pytest.mark.parametrize(
    "event",
    [
        observation_event(
            1,
            PilotId.PILOT_1,
            PilotObservationStatus.UNKNOWN,
            at_ms=0,
            quality=0.0,
            camera_available=False,
            face_visible=False,
        ),
        observation_event(
            1,
            PilotId.PILOT_1,
            PilotObservationStatus.UNKNOWN,
            at_ms=0,
            quality=0.0,
            camera_available=True,
            face_visible=False,
        ),
        observation_event(
            1,
            PilotId.PILOT_1,
            PilotObservationStatus.POSSIBLY_UNRESPONSIVE,
            at_ms=0,
            quality=0.79,
        ),
    ],
)
def test_uncertain_or_low_quality_evidence_stays_normal(event: StoredEvent) -> None:
    agent = new_agent()
    assert agent.consume_observation(event) is None
    assert agent.state == GuardianState.NORMAL


def test_repeated_unknown_duplicate_and_single_closed_eye_frame_do_not_escalate() -> None:
    agent = new_agent()
    unknowns = [
        observation_event(
            seq,
            PilotId.PILOT_1 if seq % 2 else PilotId.PILOT_2,
            PilotObservationStatus.UNKNOWN,
            at_ms=seq * 1_000,
            quality=0.0,
            camera_available=False,
            face_visible=False,
        )
        for seq in range(1, 7)
    ]
    for event in unknowns:
        assert agent.consume_observation(event) is None
    concern = observation_event(7, PilotId.PILOT_1, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=7_000)
    assert agent.consume_observation(concern) is None
    assert agent.consume_observation(concern) is None
    assert agent.state == GuardianState.SUSPECTED
    assert agent.active_incident is None


def test_responsive_observations_remain_normal() -> None:
    agent = new_agent()
    for seq, pilot in enumerate((PilotId.PILOT_1, PilotId.PILOT_2), start=1):
        assert agent.consume_observation(
            observation_event(seq, pilot, PilotObservationStatus.RESPONSIVE, at_ms=0)
        ) is None
    assert agent.state == GuardianState.NORMAL


def test_state_progression_and_dual_incident_semantics() -> None:
    agent = new_agent()
    assert agent.consume_observation(
        observation_event(1, PilotId.PILOT_1, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=0)
    ) is None
    assert agent.state == GuardianState.SUSPECTED
    assert agent.consume_observation(
        observation_event(2, PilotId.PILOT_2, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=0)
    ) is None
    assert agent.state == GuardianState.SUSPECTED
    assert agent.consume_observation(
        observation_event(3, PilotId.PILOT_1, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=1_000)
    ) is None
    assert agent.state == GuardianState.AWAITING_ACK
    incident = agent.consume_observation(
        observation_event(4, PilotId.PILOT_2, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=1_000)
    )
    assert incident is agent.active_incident
    assert agent.state == GuardianState.ESCALATED
    assert incident is not None
    assert incident.scenario_run_id == RUN_ID
    assert incident.incident_type == IncidentType.DUAL_PILOT_UNRESPONSIVE
    assert incident.severity == IncidentSeverity.CRITICAL
    assert incident.guardian_state == GuardianState.ESCALATED
    assert incident.created_at == BASE_TIME + timedelta(seconds=1)
    assert incident.acknowledgement_required is True
    assert len(incident.evidence_event_ids) == len(set(incident.evidence_event_ids)) == 4
    assert "Rule G-DET-1" in incident.explanation
    assert "quality >= 0.80" in incident.explanation
    assert len(incident.explanation) <= 1_000


def test_responsive_peer_blocks_dual_incident() -> None:
    agent = new_agent()
    seq = 1
    for at_ms in (0, 1_000, 2_000):
        agent.consume_observation(
            observation_event(seq, PilotId.PILOT_1, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=at_ms)
        )
        seq += 1
        agent.consume_observation(
            observation_event(seq, PilotId.PILOT_2, PilotObservationStatus.RESPONSIVE, at_ms=at_ms)
        )
        seq += 1
    assert agent.state == GuardianState.AWAITING_ACK
    assert agent.active_incident is None


def test_expired_concerns_do_not_combine_into_incident() -> None:
    policy = GuardianPolicy(evidence_window_ms=1_000, acknowledgement_grace_ms=0)
    agent = new_agent(policy)
    agent.consume_observation(
        observation_event(1, PilotId.PILOT_1, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=0)
    )
    agent.consume_observation(
        observation_event(2, PilotId.PILOT_1, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=500)
    )
    agent.consume_observation(
        observation_event(3, PilotId.PILOT_2, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=1_501)
    )
    agent.consume_observation(
        observation_event(4, PilotId.PILOT_2, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=2_001)
    )
    assert agent.active_incident is None


def test_processing_order_within_round_does_not_change_safety_outcome() -> None:
    evidence_sets = []
    for order in ((PilotId.PILOT_1, PilotId.PILOT_2), (PilotId.PILOT_2, PilotId.PILOT_1)):
        agent = new_agent()
        seq = 1
        expected_ids: set[UUID] = set()
        for round_number, at_ms in enumerate((0, 1_000), start=1):
            for pilot in order:
                event_id = UUID(int=30_000 + round_number * 10 + int(pilot == PilotId.PILOT_2))
                expected_ids.add(event_id)
                agent.consume_observation(
                    observation_event(
                        seq,
                        pilot,
                        PilotObservationStatus.POSSIBLY_UNRESPONSIVE,
                        at_ms=at_ms,
                        event_id=event_id,
                    )
                )
                seq += 1
        assert agent.state == GuardianState.ESCALATED
        assert agent.active_incident is not None
        evidence_sets.append(set(agent.active_incident.evidence_event_ids))
        assert evidence_sets[-1] == expected_ids
    assert evidence_sets[0] == evidence_sets[1]


def test_exactly_one_incident_is_emitted_per_episode() -> None:
    agent = new_agent()
    incident, _ = escalate(agent)
    repeated = observation_event(5, PilotId.PILOT_1, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=2_000)
    assert agent.consume_observation(repeated) is None
    assert agent.active_incident == incident


def test_matching_acknowledgement_recovers_and_duplicate_is_idempotent() -> None:
    agent = new_agent()
    incident, _ = escalate(agent)
    ack = acknowledgement(incident.incident_id)
    agent.acknowledge(ack)
    assert agent.state == GuardianState.RECOVERING
    assert agent.active_incident is None
    agent.acknowledge(ack)
    assert agent.state == GuardianState.RECOVERING


def test_stale_or_wrong_acknowledgement_is_rejected_without_clearing_incident() -> None:
    agent = new_agent()
    incident, _ = escalate(agent)
    with pytest.raises(ValueError, match="different incident"):
        agent.acknowledge(acknowledgement(UUID(int=999)))
    with pytest.raises(ValueError, match="stale scenario_run_id"):
        agent.acknowledge(acknowledgement(incident.incident_id, run_id=OTHER_RUN_ID))
    assert agent.active_incident == incident
    assert agent.state == GuardianState.ESCALATED


def test_acknowledgement_older_than_current_evidence_is_rejected() -> None:
    agent = new_agent()
    incident, _ = escalate(agent)
    stale_time = acknowledgement(incident.incident_id).model_copy(update={"acknowledged_at": BASE_TIME})
    with pytest.raises(ValueError, match="older than current evidence"):
        agent.acknowledge(stale_time)
    assert agent.active_incident == incident


def test_recovery_requires_fresh_responses_from_both_pilots() -> None:
    agent = new_agent()
    incident, _ = escalate(agent)
    agent.acknowledge(acknowledgement(incident.incident_id))
    seq = 5
    for at_ms in (2_000, 3_000):
        for pilot in PilotId:
            agent.consume_observation(observation_event(seq, pilot, PilotObservationStatus.RESPONSIVE, at_ms=at_ms))
            seq += 1
    assert agent.state == GuardianState.NORMAL


def test_new_concern_during_recovery_starts_a_new_episode() -> None:
    agent = new_agent()
    incident, _ = escalate(agent)
    agent.acknowledge(acknowledgement(incident.incident_id))
    agent.consume_observation(
        observation_event(5, PilotId.PILOT_1, PilotObservationStatus.RESPONSIVE, at_ms=2_000)
    )
    agent.consume_observation(
        observation_event(6, PilotId.PILOT_2, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=2_000)
    )
    assert agent.state == GuardianState.SUSPECTED
    assert agent.active_incident is None


def test_duplicate_and_out_of_order_events_cannot_change_state() -> None:
    agent = new_agent()
    first = observation_event(2, PilotId.PILOT_1, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=1_000)
    agent.consume_observation(first)
    assert agent.consume_observation(first) is None
    with pytest.raises(ValueError, match="out-of-order event sequence"):
        agent.consume_observation(
            observation_event(1, PilotId.PILOT_2, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=1_000)
        )
    with pytest.raises(ValueError, match="out-of-order observation time"):
        agent.consume_observation(
            observation_event(3, PilotId.PILOT_2, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=999)
        )
    assert agent.state == GuardianState.SUSPECTED


def test_reset_clears_incident_evidence_dedup_and_old_run_access() -> None:
    agent = new_agent()
    incident, events = escalate(agent)
    agent.reset(OTHER_RUN_ID)
    assert agent.state == GuardianState.NORMAL
    assert agent.active_incident is None
    assert agent.retained_event_count == 0
    with pytest.raises(ValueError, match="stale scenario_run_id"):
        agent.consume_observation(events[0])
    fresh = observation_event(
        1,
        PilotId.PILOT_1,
        PilotObservationStatus.POSSIBLY_UNRESPONSIVE,
        at_ms=0,
        run_id=OTHER_RUN_ID,
        event_id=incident.evidence_event_ids[0],
    )
    assert agent.consume_observation(fresh) is None
    assert agent.state == GuardianState.SUSPECTED


def test_quality_and_spacing_boundaries_are_inclusive() -> None:
    agent = new_agent()
    agent.consume_observation(
        observation_event(1, PilotId.PILOT_1, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=0, quality=0.80)
    )
    agent.consume_observation(
        observation_event(2, PilotId.PILOT_1, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=499, quality=0.80)
    )
    assert agent.state == GuardianState.SUSPECTED
    agent.consume_observation(
        observation_event(3, PilotId.PILOT_1, PilotObservationStatus.POSSIBLY_UNRESPONSIVE, at_ms=500, quality=0.80)
    )
    assert agent.state == GuardianState.AWAITING_ACK


@pytest.mark.parametrize(
    "kwargs",
    [
        {"minimum_observation_quality": -0.01},
        {"minimum_observation_quality": 1.01},
        {"minimum_independent_spacing_ms": 0},
        {"evidence_window_ms": 0},
        {"concerns_required_per_pilot": 1},
        {"concerns_required_per_pilot": 33, "max_evidence_per_pilot": 33},
        {"awaiting_ack_concerns": 1},
        {"acknowledgement_grace_ms": -1},
        {"recovery_observations_required_per_pilot": 0},
        {"max_evidence_per_pilot": 1},
        {"max_evidence_per_pilot": 33},
        {"max_processed_events": 4, "max_evidence_per_pilot": 3},
        {"max_acknowledgements": 0},
        {
            "minimum_independent_spacing_ms": 1_001,
            "evidence_window_ms": 1_000,
            "acknowledgement_grace_ms": 0,
        },
    ],
)
def test_invalid_policy_is_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        GuardianPolicy(**kwargs)


def test_processed_event_retention_is_bounded() -> None:
    policy = GuardianPolicy(max_evidence_per_pilot=2, max_processed_events=4)
    agent = new_agent(policy)
    for seq in range(1, 11):
        agent.consume_observation(
            observation_event(
                seq,
                PilotId.PILOT_1 if seq % 2 else PilotId.PILOT_2,
                PilotObservationStatus.RESPONSIVE,
                at_ms=seq * 1_000,
            )
        )
    assert agent.retained_event_count == 4


def test_replay_of_same_sequence_is_deterministic() -> None:
    incidents = []
    for _ in range(2):
        agent = new_agent()
        incident, _ = escalate(agent)
        incidents.append(incident)
    assert incidents[0] == incidents[1]
