"""Simulator outcome is not inferred from ATC approval.

SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.contracts.enums import AuthorizationSource, DecisionResult, SimulatorActionType
from app.contracts.models import SimulatorActionPayload
from app.main import create_app


def _app(tmp_path, name, use_real_agents):
    app = create_app(tmp_path / f"{name}-{'real' if use_real_agents else 'mock'}.db")
    if use_real_agents:
        try:
            from app.modules.guardian import DeterministicGuardianAgent
            from app.modules.sentinel import DeterministicSentinelAgent
        except ImportError:
            pytest.skip("Real Guardian/Sentinel require the merged main checkout")
        app.state.orchestrator.guardian = DeterministicGuardianAgent()
        app.state.orchestrator.sentinel = DeterministicSentinelAgent()
    return app


def _eligible(client):
    started = client.post("/api/v1/scenarios/start", json={
        "command_id": str(uuid4()), "scenario_id": "dual_pilot_atc_connected",
    })
    assert started.status_code == 200, started.text
    run_id = started.json()["snapshot"]["scenario_run_id"]
    advance = client.post("/api/v1/scenarios/advance", json={
        "command_id": str(uuid4()), "scenario_run_id": run_id, "delta_ms": 2000,
    })
    assert advance.status_code == 200, advance.text
    state = advance.json()["snapshot"]
    assert state["guardian_state"] == "ESCALATED"
    assert state["sentinel_state"] == "AWAITING_ATC"
    incident_id = state["active_incident"]["incident_id"]
    return run_id, incident_id


def _body(run_id, incident_id):
    return {
        "command_id": str(uuid4()), "scenario_run_id": run_id,
        "incident_id": incident_id, "decision": "APPROVE",
        "requested_action": "SIM_STABILIZE", "operator_id": "fictional-atc",
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }


def _history(client):
    response = client.get("/api/v1/events", params={"after_seq": 0, "limit": 100})
    assert response.status_code == 200, response.text
    return response.json()["events"]


def _assert_unconfirmed_failure(client, response, command_id):
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted"] is False
    assert body["snapshot"]["sentinel_state"] == "SIM_ACTION_RUNNING"
    assert body["snapshot"]["last_simulator_action"] is None
    assert "no successful execution recorded" in body["message"]
    assert [event["event_type"] for event in body["events"]] == [
        "ATC_DECISION", "SENTINEL_DECISION", "SENTINEL_DECISION",
    ]
    approved, failed = (body["events"][1]["payload"], body["events"][2]["payload"])
    assert approved["result"] == "APPROVED"
    assert failed["result"] == "FAILED"
    assert failed["sentinel_state"] == "SIM_ACTION_RUNNING"
    assert failed["authorization_source"] == "SIMULATED_ATC"
    assert failed["action_type"] == "SIM_STABILIZE"
    assert not any(event["event_type"] == "SIMULATOR_ACTION" for event in _history(client))
    return body


@pytest.mark.parametrize("use_real_agents", [False, True])
@pytest.mark.parametrize("error", [ValueError("simulated rejection"), RuntimeError("fault in adapter")])
def test_simulator_exception_is_audited_as_unconfirmed_not_executed(tmp_path, monkeypatch, use_real_agents, error):
    app = _app(tmp_path, "exception", use_real_agents)
    with TestClient(app) as client:
        run_id, incident_id = _eligible(client)
        simulator = app.state.orchestrator.simulator
        attempts = []

        def fail(*args):
            attempts.append(args)
            raise error

        monkeypatch.setattr(simulator, "apply_action", fail)
        command = _body(run_id, incident_id)
        first = client.post("/api/v1/atc/decision", json=command)
        first_json = _assert_unconfirmed_failure(client, first, command["command_id"])
        assert len(attempts) == 1
        before = len(_history(client))
        duplicate = client.post("/api/v1/atc/decision", json=command)
        assert duplicate.status_code == 200
        assert duplicate.json()["duplicate"] is True
        assert duplicate.json()["accepted"] is False
        assert len(_history(client)) == before
        assert len(attempts) == 1
        # Failed/unknown outcome cannot authorize a second command in the same run.
        retry = client.post("/api/v1/atc/decision", json=_body(run_id, incident_id))
        assert retry.status_code == 409, retry.text
        assert retry.json()["code"] == "AUTHORIZATION_REJECTED"
        assert first_json["snapshot"]["scenario_run_id"] == run_id
        assert len(attempts) == 1


@pytest.mark.parametrize("use_real_agents", [False, True])
@pytest.mark.parametrize("authorized,result", [
    (False, DecisionResult.FAILED),
    (True, DecisionResult.FAILED),
    (False, DecisionResult.EXECUTED),
])
def test_non_successful_payload_never_becomes_completed(tmp_path, monkeypatch, use_real_agents, authorized, result):
    app = _app(tmp_path, "non_success", use_real_agents)
    with TestClient(app) as client:
        run_id, incident_id = _eligible(client)

        def failed_action(run, action, decision, applied_at):
            return SimulatorActionPayload(
                action_id=uuid4(), scenario_run_id=run,
                action_type=action, authorization_source=AuthorizationSource.SIMULATED_ATC,
                authorized=authorized, result=result, reason="Synthetic failed outcome", applied_at=applied_at,
            )

        monkeypatch.setattr(app.state.orchestrator.simulator, "apply_action", failed_action)
        command = _body(run_id, incident_id)
        _assert_unconfirmed_failure(client, client.post("/api/v1/atc/decision", json=command), command["command_id"])


@pytest.mark.parametrize("use_real_agents", [False, True])
@pytest.mark.parametrize("corruption", ["wrong_run", "wrong_action", "wrong_source", "wrong_shape"])
def test_mismatched_or_malformed_action_confirmation_fails_closed(tmp_path, monkeypatch, use_real_agents, corruption):
    app = _app(tmp_path, "mismatch", use_real_agents)
    with TestClient(app) as client:
        run_id, incident_id = _eligible(client)

        def corrupt(run, action, decision, applied_at):
            if corruption == "wrong_shape":
                return {"authorized": True, "result": "EXECUTED"}
            return SimulatorActionPayload(
                action_id=uuid4(), scenario_run_id=uuid4() if corruption == "wrong_run" else run,
                action_type=SimulatorActionType.SIM_ABORT if corruption == "wrong_action" else action,
                authorization_source=AuthorizationSource.NONE if corruption == "wrong_source" else AuthorizationSource.SIMULATED_ATC,
                authorized=True, result=DecisionResult.EXECUTED,
                reason="Synthetic mismatched context", applied_at=applied_at,
            )

        monkeypatch.setattr(app.state.orchestrator.simulator, "apply_action", corrupt)
        command = _body(run_id, incident_id)
        _assert_unconfirmed_failure(client, client.post("/api/v1/atc/decision", json=command), command["command_id"])


@pytest.mark.parametrize("use_real_agents", [False, True])
def test_successful_simulator_action_retains_normal_completion_path(tmp_path, use_real_agents):
    app = _app(tmp_path, "success", use_real_agents)
    with TestClient(app) as client:
        run_id, incident_id = _eligible(client)
        response = client.post("/api/v1/atc/decision", json=_body(run_id, incident_id))
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["accepted"] is True
        assert body["snapshot"]["sentinel_state"] == "COMPLETED"
        assert body["snapshot"]["last_simulator_action"]["result"] == "EXECUTED"
        assert [item["event_type"] for item in body["events"]] == [
            "ATC_DECISION", "SENTINEL_DECISION", "SIMULATOR_ACTION", "SENTINEL_DECISION",
        ]
        assert body["events"][-1]["payload"]["result"] == "EXECUTED"


@pytest.mark.parametrize("use_real_agents", [False, True])
def test_completion_callback_failure_keeps_executed_action_but_not_completed(tmp_path, monkeypatch, use_real_agents):
    app = _app(tmp_path, "completion", use_real_agents)
    with TestClient(app) as client:
        run_id, incident_id = _eligible(client)

        def fail_complete():
            raise ValueError("synthetic completion acknowledgement failed")

        monkeypatch.setattr(app.state.orchestrator.sentinel, "complete_action", fail_complete)
        response = client.post("/api/v1/atc/decision", json=_body(run_id, incident_id))
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["accepted"] is False
        assert body["snapshot"]["sentinel_state"] == "SIM_ACTION_RUNNING"
        assert body["snapshot"]["last_simulator_action"]["result"] == "EXECUTED"
        assert [item["event_type"] for item in body["events"]] == [
            "ATC_DECISION", "SENTINEL_DECISION", "SIMULATOR_ACTION", "SENTINEL_DECISION",
        ]
        assert body["events"][-1]["payload"]["result"] == "FAILED"
        assert "completion failed" in body["message"]
        assert len([e for e in _history(client) if e["event_type"] == "SIMULATOR_ACTION"]) == 1
