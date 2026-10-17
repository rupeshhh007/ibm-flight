"""SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.

Focused attack chains complement existing per-input tests. I1/I2/I13 are
checked on non-approval outputs; I3-I11 on admission, replay and lifecycle edges.
"""

from copy import deepcopy
from datetime import timedelta, timezone
from uuid import UUID

import pytest

from app.contracts.enums import ATCDecisionType, DecisionResult, GuardianState, IncidentType, SentinelState, SimulatorActionType
from app.contracts.models import ATCDecision, GuardianIncident, SentinelDecision
from app.modules.sentinel import DeterministicSentinelAgent


@pytest.mark.parametrize("operations", [
    (("incident", "pending"), ("approve", "approved"), ("approve", "replayed")),
    (("incident", "pending"), ("approve", "approved"), ("complete", "ok"), ("complete", "no simulator action")),
    (("incident", "pending"), ("disconnect", "ok"), ("approve", "not awaiting")),
    (("incident", "pending"), ("disconnect", "ok"), ("reconnect", "ok"), ("approve", "not awaiting")),
    (("incident", "pending"), ("reject", "rejected"), ("reject", "replayed")),
    (("incident", "pending"), ("approve", "approved"), ("disconnect", "ok"), ("complete", "ok")),
    (("incident", "pending"), ("approve", "approved"), ("complete", "ok"), ("incident", "cannot reopen")),
    (("incident", "pending"), ("reject", "rejected"), ("disconnect", "ok"),
     ("reconnect", "ok"), ("incident", "pending"), ("approve", "approved")),
])
def test_curated_malicious_lifecycle_traces(
    atc_incident: GuardianIncident, atc_command: ATCDecision, operations: tuple[tuple[str, str], ...],
) -> None:
    agent = DeterministicSentinelAgent()
    agent.reset(atc_incident.scenario_run_id, True)
    rejection = atc_command.model_copy(update={"command_id": UUID(int=301), "decision": ATCDecisionType.REJECT})
    grants = 0
    for operation, expected in operations:
        before = deepcopy(vars(agent))
        if operation == "incident":
            call = lambda: agent.on_incident(atc_incident, atc_incident.created_at)
        elif operation in {"approve", "reject"}:
            call = lambda: agent.decide(atc_command if operation == "approve" else rejection)
        elif operation == "complete":
            call = agent.complete_action
        else:
            call = lambda: agent.set_atc_link(atc_incident.scenario_run_id, operation == "reconnect")
        if expected not in {"pending", "approved", "rejected", "ok"}:
            with pytest.raises(ValueError, match=expected):
                call()
            assert vars(agent) == before
        else:
            result = call()
            if isinstance(result, SentinelDecision):
                assert result.result.value.lower() == expected
                if result.result == DecisionResult.APPROVED:
                    grants += 1
                else:
                    assert result.action_type == SimulatorActionType.NO_OP
            else:
                assert result is None
            assert grants <= 1
        assert agent.state != SentinelState.LOCAL_FALLBACK


def test_bypass_attempts_cannot_poison_a_rejected_but_still_valid_lifecycle(
    waiting_agent: DeterministicSentinelAgent, atc_command: ATCDecision,
    atc_incident: GuardianIncident,
) -> None:
    rejected = atc_command.model_copy(update={"command_id": UUID(int=302), "decision": ATCDecisionType.REJECT})
    waiting_agent.decide(rejected)
    attacks = [
        ({"scenario_run_id": UUID(int=399)}, "scenario_run_id"),
        ({"incident_id": UUID(int=399)}, "incident_id"),
        ({"requested_action": SimulatorActionType.NO_OP}, "non-NO_OP"),
        ({"issued_at": atc_incident.created_at}, "cannot precede"),
        ({"operator_id": ""}, "operator_id"),
    ]
    for update, message in attacks:
        before = deepcopy(vars(waiting_agent))
        with pytest.raises(ValueError, match=message):
            waiting_agent.decide(atc_command.model_copy(update=update))
        assert vars(waiting_agent) == before
    for update, message in (
        ({"guardian_state": GuardianState.RECOVERING}, "ESCALATED"),
        ({"incident_type": IncidentType.PILOT_RESPONSE_REQUIRED}, "DUAL_PILOT"),
    ):
        before = deepcopy(vars(waiting_agent))
        with pytest.raises(ValueError, match=message):
            waiting_agent.on_incident(atc_incident.model_copy(update=update), atc_command.issued_at)
        assert vars(waiting_agent) == before
    assert waiting_agent.decide(atc_command).result == DecisionResult.APPROVED
    waiting_agent.complete_action()
    for number in range(310, 315):
        before = deepcopy(vars(waiting_agent))
        with pytest.raises(ValueError, match="not awaiting"):
            waiting_agent.decide(atc_command.model_copy(update={"command_id": UUID(int=number)}))
        assert vars(waiting_agent) == before


def test_first_observation_policy_allows_command_issued_before_reconnect_redelivery(
    atc_incident: GuardianIncident, atc_command: ATCDecision,
) -> None:
    """t=1 admission, link cycle, t=10 redelivery, then submit a t=4 command.

    This is allowed by current first-observation policy, not proof of freshness
    at reconnect. Rupesh/Abhinav own any stronger future policy.
    """
    agent = DeterministicSentinelAgent()
    agent.reset(atc_incident.scenario_run_id, True)
    first_time = atc_incident.created_at + timedelta(seconds=1)
    agent.on_incident(atc_incident, first_time)
    agent.set_atc_link(atc_incident.scenario_run_id, False)
    agent.set_atc_link(atc_incident.scenario_run_id, True)
    command = atc_command.model_copy(update={"issued_at": atc_incident.created_at + timedelta(seconds=4)})
    for seconds in (10, 20, 30):
        time = (atc_incident.created_at + timedelta(seconds=seconds)).astimezone(timezone(timedelta(hours=5, minutes=30)))
        assert agent.on_incident(atc_incident, time).result == DecisionResult.PENDING
        assert agent._incident_observed_at == first_time
    assert agent.decide(command).result == DecisionResult.APPROVED


def test_rapid_resets_reject_old_inputs_even_when_ids_are_reused(
    atc_incident: GuardianIncident, atc_command: ATCDecision,
) -> None:
    agent = DeterministicSentinelAgent()
    for index, stage in enumerate(("standby", "waiting", "running", "completed")):
        run_a, run_b = UUID(int=400 + index), UUID(int=500 + index)
        incident_a = atc_incident.model_copy(update={"scenario_run_id": run_a})
        command_a = atc_command.model_copy(update={"scenario_run_id": run_a})
        reject_a = command_a.model_copy(update={"command_id": UUID(int=303), "decision": ATCDecisionType.REJECT})
        agent.reset(run_a, True)
        if stage != "standby":
            agent.on_incident(incident_a, incident_a.created_at)
            agent.decide(reject_a)
        if stage in {"running", "completed"}:
            agent.decide(command_a)
        if stage == "completed":
            agent.complete_action()
        agent.reset(run_b, True)
        for call in (
            lambda: agent.on_incident(incident_a, incident_a.created_at),
            lambda: agent.decide(command_a), lambda: agent.decide(reject_a),
            lambda: agent.set_atc_link(run_a, False),
        ):
            before = deepcopy(vars(agent))
            with pytest.raises(ValueError, match="scenario_run_id"):
                call()
            assert vars(agent) == before
        # Deliberately reuse both identities with a different run, as allowed locally.
        incident_b = incident_a.model_copy(update={"scenario_run_id": run_b})
        agent.on_incident(incident_b, incident_b.created_at)
        assert agent.decide(command_a.model_copy(update={"scenario_run_id": run_b})).result == DecisionResult.APPROVED
