"""Reconnect must never grant action by itself. SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.contracts.enums import GuardianState
from app.main import create_app


def _app(tmp_path, case: str, real_agents: bool):
    app = create_app(tmp_path / f"{case}-{'real' if real_agents else 'mock'}.db")
    if real_agents:
        try:
            from app.modules.guardian import DeterministicGuardianAgent
            from app.modules.sentinel import DeterministicSentinelAgent
        except ImportError:
            pytest.skip("Real agents are only available on merged main")
        app.state.orchestrator.guardian = DeterministicGuardianAgent()
        app.state.orchestrator.sentinel = DeterministicSentinelAgent()
    return app


def _start(client, scenario):
    response = client.post("/api/v1/scenarios/start", json={
        "command_id": str(uuid4()), "scenario_id": scenario,
    })
    assert response.status_code == 200, response.text
    return response.json()["snapshot"]["scenario_run_id"]


def _advance(client, run_id, delta=2000):
    response = client.post("/api/v1/scenarios/advance", json={
        "command_id": str(uuid4()), "scenario_run_id": run_id, "delta_ms": delta,
    })
    assert response.status_code == 200, response.text
    return response.json()["snapshot"]


def _link(client, run_id, connected, command_id=None):
    response = client.post("/api/v1/communications/link", json={
        "command_id": str(command_id or uuid4()),
        "scenario_run_id": run_id,
        "atc_link_connected": connected,
        "changed_at": datetime.now(timezone.utc).isoformat(),
    })
    assert response.status_code == 200, response.text
    return response.json()


def _approve(client, run_id, incident_id):
    return client.post("/api/v1/atc/decision", json={
        "command_id": str(uuid4()), "scenario_run_id": run_id,
        "incident_id": incident_id,
        "decision": "APPROVE", "requested_action": "SIM_STABILIZE",
        "operator_id": "synthetic-atc", "issued_at": datetime.now(timezone.utc).isoformat(),
    })


def _events(client):
    response = client.get("/api/v1/events", params={"after_seq": 0, "limit": 100})
    assert response.status_code == 200, response.text
    return response.json()["events"]


def _assert_no_action(client):
    assert client.get("/api/v1/state").json()["last_simulator_action"] is None
    assert not any(event["event_type"] == "SIMULATOR_ACTION" for event in _events(client))


@pytest.mark.parametrize("real_agents", [False, True])
def test_disconnected_escalation_reconnect_redelivers_only_pending(tmp_path, real_agents):
    app = _app(tmp_path, "offline", real_agents)
    with TestClient(app) as client:
        run = _start(client, "dual_pilot_atc_disconnected")
        before = _advance(client, run)
        incident = before["active_incident"]
        assert incident is not None
        assert before["guardian_state"] == "ESCALATED"
        assert before["sentinel_state"] == "STANDBY"
        result = _link(client, run, True)
        assert result["snapshot"]["sentinel_state"] == "AWAITING_ATC"
        assert result["snapshot"]["active_incident"]["incident_id"] == incident["incident_id"]
        assert [e["event_type"] for e in result["events"]] == ["ATC_LINK_CHANGED", "SENTINEL_DECISION"]
        pending = result["events"][-1]["payload"]
        assert pending["result"] == "PENDING"
        assert pending["action_type"] == "NO_OP"
        assert pending["authorization_source"] == "NONE"
        assert pending["incident_id"] == incident["incident_id"]
        assert result["events"][-1]["causation_event_id"] == result["events"][0]["event_id"]
        _assert_no_action(client)

        # Reconnection is not approval. An explicitly authorized decision is required.
        approval = _approve(client, run, incident["incident_id"])
        assert approval.status_code == 200, approval.text
        assert approval.json()["snapshot"]["last_simulator_action"]["action_type"] == "SIM_STABILIZE"
        assert len([e for e in _events(client) if e["event_type"] == "SIMULATOR_ACTION"]) == 1


@pytest.mark.parametrize("real_agents", [False, True])
def test_connected_incident_disconnect_and_reconnect(tmp_path, real_agents):
    app = _app(tmp_path, "linkcycle", real_agents)
    with TestClient(app) as client:
        run = _start(client, "dual_pilot_atc_connected")
        before = _advance(client, run)
        assert before["sentinel_state"] == "AWAITING_ATC"
        assert _link(client, run, False)["snapshot"]["sentinel_state"] == "STANDBY"
        result = _link(client, run, True)
        assert result["snapshot"]["sentinel_state"] == "AWAITING_ATC"
        assert [e["event_type"] for e in result["events"]] == ["ATC_LINK_CHANGED", "SENTINEL_DECISION"]
        _assert_no_action(client)


@pytest.mark.parametrize("real_agents", [False, True])
def test_retired_incident_is_never_redelivered_after_ack(tmp_path, real_agents):
    app = _app(tmp_path, "retired", real_agents)
    with TestClient(app) as client:
        run = _start(client, "dual_pilot_atc_disconnected")
        incident = _advance(client, run)["active_incident"]["incident_id"]
        ack = client.post("/api/v1/pilots/acknowledge", json={
            "command_id": str(uuid4()), "scenario_run_id": run,
            "pilot_id": "PILOT_1", "alert_id": incident,
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
        })
        assert ack.status_code == 200, ack.text
        assert ack.json()["snapshot"]["active_incident"] is None
        result = _link(client, run, True)
        assert result["snapshot"]["active_incident"] is None
        assert result["snapshot"]["sentinel_state"] == "STANDBY"
        assert [e["event_type"] for e in result["events"]] == ["ATC_LINK_CHANGED"]
        approval = _approve(client, run, incident)
        assert approval.status_code == 409
        assert approval.json()["code"] == "NO_ACTIVE_INCIDENT"
        _assert_no_action(client)


@pytest.mark.parametrize("real_agents", [False, True])
def test_guardian_retirement_not_yet_in_snapshot_is_still_not_redelivered(tmp_path, real_agents):
    app = _app(tmp_path, "external-recovery", real_agents)
    with TestClient(app) as client:
        run = _start(client, "dual_pilot_atc_disconnected")
        _advance(client, run)
        guardian = app.state.orchestrator.guardian
        assert guardian.active_incident is not None
        # Independent Guardian recovery before the next API dispatch, without a
        # prior platform snapshot refresh (the critical stale-state regression).
        guardian._active_incident = None
        guardian._state = GuardianState.RECOVERING
        result = _link(client, run, True)
        assert result["snapshot"]["active_incident"] is None
        assert result["snapshot"]["sentinel_state"] == "STANDBY"
        assert [e["event_type"] for e in result["events"]] == ["ATC_LINK_CHANGED"]
        _assert_no_action(client)


@pytest.mark.parametrize("real_agents", [False, True])
def test_reconnect_does_not_redeliver_changed_unsynchronized_incident(tmp_path, real_agents):
    app = _app(tmp_path, "unsynchronized", real_agents)
    with TestClient(app) as client:
        run = _start(client, "dual_pilot_atc_disconnected")
        old = _advance(client, run)["active_incident"]["incident_id"]
        guardian = app.state.orchestrator.guardian
        guardian._active_incident = guardian.active_incident.model_copy(update={"incident_id": uuid4()})
        result = _link(client, run, True)
        assert result["snapshot"]["sentinel_state"] == "STANDBY"
        assert [e["event_type"] for e in result["events"]] == ["ATC_LINK_CHANGED"]
        assert _approve(client, run, old).status_code == 409
        _assert_no_action(client)


@pytest.mark.parametrize("real_agents", [False, True])
def test_repeated_link_updates_do_not_duplicate_handoffs(tmp_path, real_agents):
    app = _app(tmp_path, "repeat", real_agents)
    with TestClient(app) as client:
        run = _start(client, "dual_pilot_atc_disconnected")
        _advance(client, run)
        first_id = uuid4()
        first = _link(client, run, True, first_id)
        assert [e["event_type"] for e in first["events"]] == ["ATC_LINK_CHANGED", "SENTINEL_DECISION"]
        before = len(_events(client))
        response = client.post("/api/v1/communications/link", json={
            "command_id": str(first_id), "scenario_run_id": run,
            "atc_link_connected": True,
            "changed_at": first["snapshot"]["communication"]["last_change_at"],
        })
        assert response.status_code == 200, response.text
        assert response.json()["duplicate"] is True
        assert len(_events(client)) == before
        second = _link(client, run, True)
        assert [e["event_type"] for e in second["events"]] == ["ATC_LINK_CHANGED"]
        assert len(_events(client)) == before + 1
        _assert_no_action(client)


@pytest.mark.parametrize("real_agents", [False, True])
def test_no_incident_connect_disconnect_never_grants_or_delivers(tmp_path, real_agents):
    app = _app(tmp_path, "normal", real_agents)
    with TestClient(app) as client:
        run = _start(client, "normal_flight")
        disconnected = _link(client, run, False)
        assert disconnected["snapshot"]["sentinel_state"] == "STANDBY"
        reconnected = _link(client, run, True)
        assert reconnected["snapshot"]["sentinel_state"] == "STANDBY"
        assert [e["event_type"] for e in reconnected["events"]] == ["ATC_LINK_CHANGED"]
        _assert_no_action(client)


def test_reset_before_reconnect_rejects_old_run(tmp_path):
    app = _app(tmp_path, "reset", False)
    with TestClient(app) as client:
        run = _start(client, "dual_pilot_atc_disconnected")
        _advance(client, run)
        reset = client.post("/api/v1/scenarios/reset", json={
            "command_id": str(uuid4()), "scenario_run_id": run,
        })
        assert reset.status_code == 200, reset.text
        response = client.post("/api/v1/communications/link", json={
            "command_id": str(uuid4()), "scenario_run_id": run,
            "atc_link_connected": True,
            "changed_at": datetime.now(timezone.utc).isoformat(),
        })
        assert response.status_code == 409
        assert response.json()["code"] == "STALE_SCENARIO_RUN"
        _assert_no_action(client)


@pytest.mark.parametrize("real_agents", [False, True])
def test_completed_action_does_not_reopen_on_link_reconnect(tmp_path, real_agents):
    app = _app(tmp_path, "completed", real_agents)
    with TestClient(app) as client:
        run = _start(client, "dual_pilot_atc_connected")
        incident = _advance(client, run)["active_incident"]["incident_id"]
        approved = _approve(client, run, incident)
        assert approved.status_code == 200, approved.text
        assert approved.json()["snapshot"]["sentinel_state"] == "COMPLETED"
        _link(client, run, False)
        reconnected = _link(client, run, True)
        assert reconnected["snapshot"]["sentinel_state"] == "COMPLETED"
        assert [event["event_type"] for event in reconnected["events"]] == ["ATC_LINK_CHANGED"]
        assert len([event for event in _events(client) if event["event_type"] == "SIMULATOR_ACTION"]) == 1
        assert _approve(client, run, incident).status_code == 409


def test_failed_redelivery_does_not_leave_an_unrecorded_link_mutation(tmp_path):
    from app.modules.sentinel.mock import MockSentinelAgent

    class RejectOnSecondDelivery(MockSentinelAgent):
        def on_incident(self, incident, observed_at):
            if self._incident is not None and self._atc_connected:
                raise ValueError("refusing the retained incident")
            return super().on_incident(incident, observed_at)

    app = _app(tmp_path, "redelivery-failed", False)
    app.state.orchestrator.sentinel = RejectOnSecondDelivery()
    with TestClient(app) as client:
        run = _start(client, "dual_pilot_atc_disconnected")
        incident = _advance(client, run)["active_incident"]["incident_id"]
        result = _link(client, run, True)
        assert result["accepted"] is True
        assert "redelivery rejected" in result["message"]
        assert result["snapshot"]["sentinel_state"] == "STANDBY"
        assert result["snapshot"]["communication"]["atc_link_connected"] is True
        assert [event["event_type"] for event in result["events"]] == ["ATC_LINK_CHANGED"]
        assert _approve(client, run, incident).status_code == 409
        _assert_no_action(client)
