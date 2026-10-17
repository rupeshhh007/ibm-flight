from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient


def _start(client: TestClient, scenario_id: str) -> dict:
    response = client.post(
        "/api/v1/scenarios/start",
        json={"command_id": str(uuid4()), "scenario_id": scenario_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _advance(client: TestClient, run_id: str, delta_ms: int = 1_000) -> dict:
    response = client.post(
        "/api/v1/scenarios/advance",
        json={"command_id": str(uuid4()), "scenario_run_id": run_id, "delta_ms": delta_ms},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _escalate(client: TestClient) -> tuple[str, str]:
    started = _start(client, "dual_pilot_atc_connected")
    run_id = started["snapshot"]["scenario_run_id"]
    _advance(client, run_id)
    result = _advance(client, run_id)
    incident_id = result["snapshot"]["active_incident"]["incident_id"]
    assert len(result["snapshot"]["active_incident"]["evidence_event_ids"]) == 4
    assert "Rule G-P0-1" in result["snapshot"]["active_incident"]["explanation"]
    assert result["snapshot"]["sentinel_state"] == "AWAITING_ATC"
    assert result["snapshot"]["last_simulator_action"] is None
    return run_id, incident_id


def test_health_state_and_catalog(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok", "simulation_only": True}
    assert client.get("/readyz").status_code == 200
    state = client.get("/api/v1/state")
    assert state.status_code == 200
    assert state.json()["scenario_run_id"] is None
    assert len(client.get("/api/v1/scenarios").json()["scenarios"]) == 5


def test_normal_flight_never_escalates_or_acts(client: TestClient) -> None:
    started = _start(client, "normal_flight")
    run_id = started["snapshot"]["scenario_run_id"]
    _advance(client, run_id)
    result = _advance(client, run_id)
    assert result["snapshot"]["guardian_state"] == "NORMAL"
    assert result["snapshot"]["active_incident"] is None
    assert result["snapshot"]["last_simulator_action"] is None


def test_scenario_outcomes_are_deterministic_except_identity_and_sequence(client: TestClient) -> None:
    outcomes = []
    for _ in range(2):
        started = _start(client, "single_pilot_unresponsive")
        run_id = started["snapshot"]["scenario_run_id"]
        _advance(client, run_id)
        result = _advance(client, run_id)["snapshot"]
        outcomes.append(
            {
                "guardian_state": result["guardian_state"],
                "sentinel_state": result["sentinel_state"],
                "pilot_statuses": [item["latest_observation"]["observation_status"] for item in result["pilots"]],
                "telemetry": {
                    "altitude_ft": result["telemetry"]["altitude_ft"],
                    "airspeed_kts": result["telemetry"]["airspeed_kts"],
                },
            }
        )
    assert outcomes[0] == outcomes[1]


def test_connected_emergency_waits_rejects_then_executes_exactly_once(client: TestClient) -> None:
    run_id, incident_id = _escalate(client)
    rejection = client.post(
        "/api/v1/atc/decision",
        json={
            "command_id": str(uuid4()),
            "scenario_run_id": run_id,
            "incident_id": incident_id,
            "decision": "REJECT",
            "requested_action": "SIM_STABILIZE",
            "operator_id": "fictional-atc",
            "issued_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert rejection.status_code == 200
    assert rejection.json()["snapshot"]["last_simulator_action"] is None
    command_id = str(uuid4())
    approval_body = {
        "command_id": command_id,
        "scenario_run_id": run_id,
        "incident_id": incident_id,
        "decision": "APPROVE",
        "requested_action": "SIM_STABILIZE",
        "operator_id": "fictional-atc",
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    approval = client.post("/api/v1/atc/decision", json=approval_body)
    assert approval.status_code == 200, approval.text
    assert approval.json()["snapshot"]["last_simulator_action"]["action_type"] == "SIM_STABILIZE"
    replay = client.post("/api/v1/atc/decision", json=approval_body)
    assert replay.status_code == 200
    assert replay.json()["duplicate"] is True
    actions = [
        event
        for event in client.get("/api/v1/events", params={"after_seq": 0, "limit": 100}).json()["events"]
        if event["event_type"] == "SIMULATOR_ACTION"
    ]
    assert len(actions) == 1


def test_single_responsive_pilot_and_camera_unknown_never_act(client: TestClient) -> None:
    for scenario_id in ("single_pilot_unresponsive", "camera_obstructed"):
        started = _start(client, scenario_id)
        run_id = started["snapshot"]["scenario_run_id"]
        _advance(client, run_id)
        result = _advance(client, run_id)
        assert result["snapshot"]["active_incident"] is None
        assert result["snapshot"]["last_simulator_action"] is None
        if scenario_id == "camera_obstructed":
            assert all(
                pilot["latest_observation"]["observation_status"] == "UNKNOWN"
                for pilot in result["snapshot"]["pilots"]
            )


def test_disconnect_alone_does_not_authorize_fallback(client: TestClient) -> None:
    started = _start(client, "normal_flight")
    run_id = started["snapshot"]["scenario_run_id"]
    response = client.post(
        "/api/v1/communications/link",
        json={
            "command_id": str(uuid4()),
            "scenario_run_id": run_id,
            "atc_link_connected": False,
            "changed_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 200
    assert response.json()["snapshot"]["last_simulator_action"] is None


def test_current_run_pilot_acknowledgement_enters_recovery(client: TestClient) -> None:
    run_id, incident_id = _escalate(client)
    response = client.post(
        "/api/v1/pilots/acknowledge",
        json={
            "command_id": str(uuid4()),
            "scenario_run_id": run_id,
            "pilot_id": "PILOT_1",
            "alert_id": incident_id,
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["snapshot"]["guardian_state"] == "RECOVERING"
    assert response.json()["snapshot"]["active_incident"] is None


def test_reset_preserves_history_and_rejects_old_run(client: TestClient) -> None:
    old_run, incident_id = _escalate(client)
    before = client.get("/api/v1/events").json()["latest_event_seq"]
    reset = client.post(
        "/api/v1/scenarios/reset",
        json={"command_id": str(uuid4()), "scenario_run_id": old_run},
    )
    assert reset.status_code == 200
    assert reset.json()["snapshot"]["scenario_run_id"] != old_run
    assert client.get("/api/v1/events").json()["latest_event_seq"] > before
    stale = client.post(
        "/api/v1/scenarios/advance",
        json={"command_id": str(uuid4()), "scenario_run_id": old_run, "delta_ms": 1_000},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_SCENARIO_RUN"
    stale_approval = client.post(
        "/api/v1/atc/decision",
        json={
            "command_id": str(uuid4()),
            "scenario_run_id": old_run,
            "incident_id": incident_id,
            "decision": "APPROVE",
            "requested_action": "SIM_STABILIZE",
            "operator_id": "fictional-atc",
            "issued_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert stale_approval.status_code == 409
    assert reset.json()["snapshot"]["last_simulator_action"] is None


def test_wrong_incident_invalid_action_and_conflicting_duplicate_are_safe(client: TestClient) -> None:
    run_id, incident_id = _escalate(client)
    wrong = client.post(
        "/api/v1/atc/decision",
        json={
            "command_id": str(uuid4()),
            "scenario_run_id": run_id,
            "incident_id": str(uuid4()),
            "decision": "APPROVE",
            "requested_action": "SIM_STABILIZE",
            "operator_id": "fictional-atc",
            "issued_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert wrong.status_code == 409
    invalid = client.post(
        "/api/v1/atc/decision",
        json={
            "command_id": str(uuid4()),
            "scenario_run_id": run_id,
            "incident_id": incident_id,
            "decision": "APPROVE",
            "requested_action": "LAND_REAL_AIRCRAFT",
            "operator_id": "fictional-atc",
            "issued_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert invalid.status_code == 422
    command_id = str(uuid4())
    first = client.post(
        "/api/v1/scenarios/advance",
        json={"command_id": command_id, "scenario_run_id": run_id, "delta_ms": 1},
    )
    assert first.status_code == 200
    conflict = client.post(
        "/api/v1/scenarios/advance",
        json={"command_id": command_id, "scenario_run_id": run_id, "delta_ms": 2},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "COMMAND_ID_CONFLICT"


def test_event_history_limit_is_bounded_and_after_seq_is_honored(client: TestClient) -> None:
    _start(client, "normal_flight")
    first = client.get("/api/v1/events", params={"after_seq": 0, "limit": 1})
    assert first.status_code == 200
    assert len(first.json()["events"]) == 1
    seq = first.json()["events"][0]["seq"]
    later = client.get("/api/v1/events", params={"after_seq": seq, "limit": 100})
    assert all(item["seq"] > seq for item in later.json()["events"])
    assert client.get("/api/v1/events", params={"limit": 501}).status_code == 422
