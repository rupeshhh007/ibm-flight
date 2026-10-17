"""SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.

I1-I11/I13: an independent eligibility ledger checks every event outcome,
authorization count, and failure nonmutation. I12: simulator execution is trapped.
The ledger tracks permission facts, not production transition tables or JSON.
"""

from copy import deepcopy
from datetime import timedelta
from random import Random
from uuid import UUID

import pytest

from app.contracts.enums import ATCDecisionType, AuthorizationSource, DecisionResult, SentinelState
from app.contracts.models import ATCDecision, GuardianIncident
from app.modules.sentinel import DeterministicSentinelAgent
from app.modules.simulator import MockAircraftSimulator


SEED = 0xA3E004
OPERATIONS = (
    "incident", "approve", "reject", "replay", "conflict",
    "disconnect", "reconnect", "reset", "complete", "stale",
)


def test_one_hundred_seeded_sequences_check_invariants_after_every_event(
    atc_incident: GuardianIncident, atc_command: ATCDecision, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_execution(*args: object, **kwargs: object) -> None:
        raise AssertionError("Sentinel invoked the simulator")

    for method in ("start", "advance", "apply_action", "reset"):
        monkeypatch.setattr(MockAircraftSimulator, method, forbidden_execution)
    totals = {"approved": 0, "rejected": 0, "completed": 0, "invalid": 0}
    for sequence in range(100):
        seed = SEED + sequence
        random = Random(seed)
        # Every sequence contains every operation, with varied interleaving.
        operations = list(OPERATIONS) * 2 + random.choices(OPERATIONS, k=4)
        random.shuffle(operations)
        # Exercise successful paths too, not just rejection-heavy random traffic.
        operations[:0] = ["incident", "reject", "approve", "complete"]
        agent = DeterministicSentinelAgent()
        run_number = seed * 100
        run_id = UUID(int=run_number)
        agent.reset(run_id, True)
        incident = atc_incident.model_copy(update={"scenario_run_id": run_id})
        connected = True
        admitted = waiting = authorized = completed = False
        first_observation = None
        consumed: dict[UUID, ATCDecision] = {}
        history: list[ATCDecision] = []
        grants: dict[UUID, int] = {run_id: 0}
        authorization = None
        trace: list[str] = []

        for step, operation in enumerate(operations):
            now = atc_incident.created_at + timedelta(seconds=step + 1)
            command = atc_command.model_copy(update={
                "command_id": UUID(int=seed * 10000 + step),
                "scenario_run_id": run_id, "issued_at": now,
            })
            if operation == "reject":
                command.decision = ATCDecisionType.REJECT
            if operation in {"replay", "conflict"} and history:
                command = random.choice(history).model_copy(deep=True)
                if operation == "conflict":
                    command.operator_id += "-conflict"
            if operation == "stale":
                command.scenario_run_id = UUID(int=run_number - 1)
            trace.append(f"{step}: {operation} run={run_id} command={command.model_dump_json()}")
            before = deepcopy(vars(agent))
            try:
                if operation in {"approve", "reject", "replay", "conflict", "stale"}:
                    eligible = (
                        admitted and waiting and connected and not authorized and not completed
                        and command.scenario_run_id == run_id
                        and command.incident_id == incident.incident_id
                        and command.command_id not in consumed
                        and first_observation is not None
                        and command.issued_at >= first_observation
                    )
                    try:
                        result = agent.decide(command)
                    except ValueError as error:
                        assert not eligible, str(error)
                        assert vars(agent) == before
                        if command.command_id in consumed:
                            expected_text = "replayed command_id" if command == consumed[command.command_id] else "command_id conflict"
                            assert expected_text in str(error)
                        totals["invalid"] += 1
                    else:
                        assert eligible, "authorization boundary accepted an ineligible command"
                        consumed[command.command_id] = command.model_copy(deep=True)
                        history.append(command.model_copy(deep=True))
                        if command.decision == ATCDecisionType.APPROVE:
                            assert result.result == DecisionResult.APPROVED
                            assert result.authorization_source == AuthorizationSource.SIMULATED_ATC
                            assert result.scenario_run_id == run_id
                            assert result.incident_id == incident.incident_id
                            assert result.evidence_event_ids == incident.evidence_event_ids
                            assert grants[run_id] == 0
                            grants[run_id] += 1
                            authorized = True
                            waiting = False
                            authorization = result.model_copy(deep=True)
                            totals["approved"] += 1
                        else:
                            assert result.result == DecisionResult.REJECTED
                            assert result.action_type.value == "NO_OP"
                            totals["rejected"] += 1
                elif operation == "incident":
                    if authorized or completed:
                        with pytest.raises(ValueError, match="cannot reopen"):
                            agent.on_incident(incident, now)
                        assert vars(agent) == before
                        totals["invalid"] += 1
                    else:
                        result = agent.on_incident(incident, now)
                        assert result.result == DecisionResult.PENDING
                        assert result.action_type.value == "NO_OP"
                        assert result.authorization_source == AuthorizationSource.NONE
                        if not admitted:
                            first_observation = now
                        admitted = True
                        waiting = connected
                elif operation in {"disconnect", "reconnect"}:
                    connected = operation == "reconnect"
                    assert agent.set_atc_link(run_id, connected) is None
                    if not connected:
                        waiting = False
                elif operation == "complete":
                    if authorized and not completed:
                        assert agent.complete_action() is None
                        completed = True
                        totals["completed"] += 1
                    else:
                        with pytest.raises(ValueError, match="no simulator action is running"):
                            agent.complete_action()
                        assert vars(agent) == before
                        totals["invalid"] += 1
                else:
                    assert operation == "reset"
                    run_number += 1
                    run_id = UUID(int=run_number)
                    connected = random.choice((True, False))
                    trace.append(f"reset target run={run_id} connected={connected}")
                    agent.reset(run_id, connected)
                    incident = incident.model_copy(update={"scenario_run_id": run_id})
                    admitted = waiting = authorized = completed = False
                    first_observation = authorization = None
                    consumed.clear()
                    grants[run_id] = 0

                # Global assertions run after every successful or rejected event.
                expected_state = (
                    SentinelState.COMPLETED if completed else
                    SentinelState.SIM_ACTION_RUNNING if authorized else
                    SentinelState.AWAITING_ATC if waiting else SentinelState.STANDBY
                )
                assert agent.state == expected_state
                assert all(count <= 1 for count in grants.values())
                assert agent._authorization == authorization
                assert len(agent._consumed_commands) == len(consumed)
                assert agent._incident_observed_at == first_observation
                assert agent.state != SentinelState.LOCAL_FALLBACK
            except Exception as error:
                raise AssertionError(f"seed={seed}; complete operation trace:\n" + "\n".join(trace)) from error

    # Prove the generator actually exercised successful workflows and failures.
    assert totals["approved"] >= 100
    assert totals["rejected"] >= 100
    assert totals["completed"] >= 100
    assert totals["invalid"] >= 100
