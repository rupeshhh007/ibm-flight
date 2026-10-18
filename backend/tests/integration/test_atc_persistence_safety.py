"""Durable-intent and fail-closed ATC replay boundary tests.

SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
This does not claim external side effects and SQLite are atomically committed.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.contracts.enums import EventType
from app.main import create_app


def _app(tmp_path, use_real_agents, suffix):
    app = create_app(tmp_path / f"journal-{suffix}-{use_real_agents}.db")
    if use_real_agents:
        try:
            from app.modules.guardian import DeterministicGuardianAgent
            from app.modules.sentinel import DeterministicSentinelAgent
        except ImportError:
            pytest.skip("Merged Guardian and Sentinel modules not available in archived fixture")
        app.state.orchestrator.guardian = DeterministicGuardianAgent()
        app.state.orchestrator.sentinel = DeterministicSentinelAgent()
    return app


def _eligible(client):
    started = client.post("/api/v1/scenarios/start", json={
        "command_id": str(uuid4()), "scenario_id": "dual_pilot_atc_connected",
    })
    assert started.status_code == 200, started.text
    run_id = started.json()["snapshot"]["scenario_run_id"]
    advanced = client.post("/api/v1/scenarios/advance", json={
        "command_id": str(uuid4()), "scenario_run_id": run_id, "delta_ms": 2000,
    })
    assert advanced.status_code == 200, advanced.text
    snapshot = advanced.json()["snapshot"]
    assert snapshot["guardian_state"] == "ESCALATED"
    assert snapshot["sentinel_state"] == "AWAITING_ATC"
    return run_id, snapshot["active_incident"]["incident_id"]


def _decision(run_id, incident_id, choice="APPROVE"):
    return {
        "command_id": str(uuid4()), "scenario_run_id": run_id,
        "incident_id": incident_id, "decision": choice,
        "requested_action": "SIM_STABILIZE", "operator_id": "fictional-atc",
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }


def _all_events(store):
    output = []
    after_seq = 0
    while True:
        batch = store.read_after(after_seq, 500)
        if not batch:
            return output
        output.extend(batch)
        after_seq = batch[-1].seq


def _actions(events):
    return [x for x in events if x.event_type == EventType.SIMULATOR_ACTION]


@pytest.mark.parametrize("use_real_agents", [False, True])
def test_durable_atc_intent_is_present_before_simulator_side_effect(tmp_path, monkeypatch, use_real_agents):
    app = _app(tmp_path, use_real_agents, "ordering")
    with TestClient(app) as client:
        run_id, incident_id = _eligible(client)
        orchestrator = app.state.orchestrator
        real_apply = orchestrator.simulator.apply_action
        observed_before_action = []

        def inspect_intent(*args):
            events = _all_events(orchestrator.store)
            intent = [event for event in events if event.event_type == EventType.ATC_DECISION]
            approved = [event for event in events if event.event_type == EventType.SENTINEL_DECISION and event.payload.result == "APPROVED"]
            assert len(intent) == len(approved) == 1
            assert len(_actions(events)) == 0
            observed_before_action.append((intent[0].seq, approved[0].seq))
            return real_apply(*args)

        monkeypatch.setattr(orchestrator.simulator, "apply_action", inspect_intent)
        command = _decision(run_id, incident_id)
        response = client.post("/api/v1/atc/decision", json=command)
        assert response.status_code == 200, response.text
        assert response.json()["accepted"] is True
        assert len(observed_before_action) == 1
        assert [e["event_type"] for e in response.json()["events"]] == [
            "ATC_DECISION", "SENTINEL_DECISION", "SIMULATOR_ACTION", "SENTINEL_DECISION",
        ]
        assert len(_actions(_all_events(orchestrator.store))) == 1
        assert client.post("/api/v1/atc/decision", json=command).json()["duplicate"] is True
        assert len(observed_before_action) == 1


@pytest.mark.parametrize("use_real_agents", [False, True])
def test_intent_storage_failure_prevents_simulator_execution(tmp_path, monkeypatch, use_real_agents):
    app = _app(tmp_path, use_real_agents, "intent-fail")
    with TestClient(app) as client:
        run_id, incident_id = _eligible(client)
        o = app.state.orchestrator
        original_append = o.store.append
        original_apply = o.simulator.apply_action
        attempts = []

        def failed_intent(events):
            if any(e.event_type == EventType.ATC_DECISION for e in events):
                raise OSError("synthetic disk write failure before action")
            return original_append(events)

        def inspect_apply(*args):
            attempts.append(args)
            return original_apply(*args)

        monkeypatch.setattr(o.store, "append", failed_intent)
        monkeypatch.setattr(o.simulator, "apply_action", inspect_apply)
        command = _decision(run_id, incident_id)
        response = client.post("/api/v1/atc/decision", json=command)
        assert response.status_code == 503, response.text
        assert response.json()["code"] == "ATC_INTENT_UNAVAILABLE"
        assert attempts == []
        assert not any(e.event_type == EventType.ATC_DECISION for e in _all_events(o.store))
        # Sentinel has already consumed the permission, so retry fails closed.
        monkeypatch.setattr(o.store, "append", original_append)
        retry = client.post("/api/v1/atc/decision", json=command)
        assert retry.status_code == 409
        assert len(attempts) == 0


@pytest.mark.parametrize("use_real_agents", [False, True])
def test_late_event_append_failure_does_not_repeat_simulator_side_effect(tmp_path, monkeypatch, use_real_agents):
    app = _app(tmp_path, use_real_agents, "late-append")
    with TestClient(app) as client:
        run_id, incident_id = _eligible(client)
        o = app.state.orchestrator
        real_append = o.store.append
        real_apply = o.simulator.apply_action
        calls = []

        def fail_outcome(events):
            if any(e.event_type == EventType.SIMULATOR_ACTION for e in events):
                raise OSError("synthetic late commit failure")
            return real_append(events)

        def counted(*args):
            calls.append(args)
            return real_apply(*args)

        monkeypatch.setattr(o.store, "append", fail_outcome)
        monkeypatch.setattr(o.simulator, "apply_action", counted)
        command = _decision(run_id, incident_id)
        failure = client.post("/api/v1/atc/decision", json=command)
        assert failure.status_code == 503, failure.text
        assert failure.json()["code"] == "ATC_OUTCOME_UNCERTAIN"
        assert len(calls) == 1
        history = _all_events(o.store)
        assert len([e for e in history if e.event_type == EventType.ATC_DECISION]) == 1
        assert not _actions(history)  # Side effect occurred; audit could not be completed.

        monkeypatch.setattr(o.store, "append", real_append)
        exact_retry = client.post("/api/v1/atc/decision", json=command)
        assert exact_retry.status_code == 409
        assert exact_retry.json()["code"] == "COMMAND_OUTCOME_UNCERTAIN"
        assert len(calls) == 1
        conflicting = {**command, "operator_id": "different-operator"}
        altered_retry = client.post("/api/v1/atc/decision", json=conflicting)
        assert altered_retry.status_code == 409
        assert altered_retry.json()["code"] == "COMMAND_ID_CONFLICT"
        assert len(calls) == 1
        new_command = client.post("/api/v1/atc/decision", json=_decision(run_id, incident_id))
        assert new_command.status_code == 409
        assert len(calls) == 1


@pytest.mark.parametrize("use_real_agents", [False, True])
def test_missing_cached_command_result_is_detected_from_durable_intent(tmp_path, monkeypatch, use_real_agents):
    app = _app(tmp_path, use_real_agents, "record-failure")
    with TestClient(app) as client:
        run_id, incident_id = _eligible(client)
        o = app.state.orchestrator
        original_record = o.store.record_command
        real_apply = o.simulator.apply_action
        calls = []

        def fail_atc_record(record):
            if record.command_id == command_uuid:
                raise OSError("synthetic command results unavailable")
            return original_record(record)

        def counted(*args):
            calls.append(args)
            return real_apply(*args)

        command = _decision(run_id, incident_id)
        command_uuid = UUID(command["command_id"])
        monkeypatch.setattr(o.store, "record_command", fail_atc_record)
        monkeypatch.setattr(o.simulator, "apply_action", counted)
        response = client.post("/api/v1/atc/decision", json=command)
        assert response.status_code == 503, response.text
        assert response.json()["code"] == "ATC_RESULT_CACHE_UNAVAILABLE"
        assert len(calls) == 1
        assert len(_actions(_all_events(o.store))) == 1
        assert o.store.get_command(command_uuid) is None

        monkeypatch.setattr(o.store, "record_command", original_record)
        duplicate = client.post("/api/v1/atc/decision", json=command)
        assert duplicate.status_code == 409
        assert duplicate.json()["code"] == "COMMAND_OUTCOME_UNCERTAIN"
        assert len(calls) == 1


@pytest.mark.parametrize("use_real_agents", [False, True])
def test_rejected_command_durable_audit_prevents_uncached_same_id_replay(tmp_path, monkeypatch, use_real_agents):
    app = _app(tmp_path, use_real_agents, "reject-record")
    with TestClient(app) as client:
        run_id, incident_id = _eligible(client)
        o = app.state.orchestrator
        original_record = o.store.record_command
        command = _decision(run_id, incident_id, "REJECT")
        command_uuid = UUID(command["command_id"])

        def fail_one(record):
            if record.command_id == command_uuid:
                raise OSError("synthetic rejection result cache failure")
            return original_record(record)

        monkeypatch.setattr(o.store, "record_command", fail_one)
        response = client.post("/api/v1/atc/decision", json=command)
        assert response.status_code == 503
        assert response.json()["code"] == "ATC_RESULT_CACHE_UNAVAILABLE"
        assert not _actions(_all_events(o.store))
        monkeypatch.setattr(o.store, "record_command", original_record)
        duplicate = client.post("/api/v1/atc/decision", json=command)
        assert duplicate.status_code == 409
        assert duplicate.json()["code"] == "COMMAND_OUTCOME_UNCERTAIN"
        assert not _actions(_all_events(o.store))


@pytest.mark.parametrize("use_real_agents", [False, True])
def test_failed_event_publisher_before_action_blocks_execution(tmp_path, monkeypatch, use_real_agents):
    app = _app(tmp_path, use_real_agents, "publisher-fail")
    with TestClient(app) as client:
        run_id, incident_id = _eligible(client)
        o = app.state.orchestrator
        applied = []

        def fail_publish(events):
            raise RuntimeError("synthetic event fanout failure")

        real_apply = o.simulator.apply_action
        def count_apply(*args):
            applied.append(args)
            return real_apply(*args)

        monkeypatch.setattr(o.publisher, "publish", fail_publish)
        monkeypatch.setattr(o.simulator, "apply_action", count_apply)
        command = _decision(run_id, incident_id)
        response = client.post("/api/v1/atc/decision", json=command)
        assert response.status_code == 503
        assert response.json()["code"] == "ATC_INTENT_UNAVAILABLE"
        assert applied == []
        assert len([e for e in _all_events(o.store) if e.event_type == EventType.ATC_DECISION]) == 1
        retry = client.post("/api/v1/atc/decision", json=command)
        assert retry.status_code == 409
        assert retry.json()["code"] == "COMMAND_OUTCOME_UNCERTAIN"
        assert len(applied) == 0


@pytest.mark.parametrize("use_real_agents", [False, True])
def test_silent_partial_intent_append_cannot_start_simulator(tmp_path, monkeypatch, use_real_agents):
    app = _app(tmp_path, use_real_agents, "partial-intent")
    with TestClient(app) as client:
        run_id, incident_id = _eligible(client)
        o = app.state.orchestrator
        original_append = o.store.append
        original_apply = o.simulator.apply_action
        calls = []

        def disappear_intent(events):
            if any(e.event_type == EventType.ATC_DECISION for e in events):
                return []
            return original_append(events)

        def counted(*args):
            calls.append(args)
            return original_apply(*args)

        monkeypatch.setattr(o.store, "append", disappear_intent)
        monkeypatch.setattr(o.simulator, "apply_action", counted)
        cmd = _decision(run_id, incident_id)
        response = client.post("/api/v1/atc/decision", json=cmd)
        assert response.status_code == 503
        assert response.json()["code"] == "ATC_INTENT_UNAVAILABLE"
        assert not calls
        assert not any(e.event_type == EventType.ATC_DECISION for e in _all_events(o.store))
