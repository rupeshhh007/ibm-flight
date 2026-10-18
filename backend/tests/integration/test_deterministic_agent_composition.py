"""SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.

HTTP-boundary safety checks for the opt-in deterministic Guardian/Sentinel pair.
The default mock API and its OpenAPI contract must remain unchanged.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def _client(tmp_path: Path, *, mode: str = "deterministic") -> TestClient:
    return TestClient(create_app(tmp_path / f"{uuid4()}.db", agent_mode=mode))


def _post(client: TestClient, route: str, **fields: object):
    return client.post(route, json={"command_id": str(uuid4()), **fields})


def _start(client: TestClient, scenario: str) -> dict:
    response = _post(client, "/api/v1/scenarios/start", scenario_id=scenario)
    assert response.status_code == 200, response.text
    assert response.json()["snapshot"]["last_simulator_action"] is None
    return response.json()["snapshot"]


def _advance(client: TestClient, run_id: str, ms: int = 1000) -> dict:
    response = _post(
        client, "/api/v1/scenarios/advance", scenario_run_id=run_id, delta_ms=ms
    )
    assert response.status_code == 200, response.text
    return response.json()["snapshot"]


def _incident(client: TestClient, scenario: str = "dual_pilot_atc_connected", *,
              batch: bool = False) -> tuple[str, dict, dict]:
    started = _start(client, scenario)
    run_id = started["scenario_run_id"]
    if batch:
        snapshot = _advance(client, run_id, 2000)
    else:
        _advance(client, run_id)
        snapshot = _advance(client, run_id)
    incident = snapshot["active_incident"]
    assert incident is not None, snapshot
    assert snapshot["guardian_state"] == "ESCALATED"
    assert snapshot["last_simulator_action"] is None
    assert len(incident["evidence_event_ids"]) == 4
    return run_id, incident, snapshot


def _atc(client: TestClient, run_id: str, incident_id: str,
         issued_at: str, *, decision: str = "APPROVE", command_id: str | None = None):
    payload = {
        "command_id": command_id or str(uuid4()),
        "scenario_run_id": run_id,
        "incident_id": incident_id,
        "decision": decision,
        "requested_action": "SIM_STABILIZE",
        "operator_id": "fictional-atc",
        "issued_at": issued_at,
    }
    return client.post("/api/v1/atc/decision", json=payload), payload


def _link(client: TestClient, run_id: str, connected: bool, at: str):
    return _post(
        client,
        "/api/v1/communications/link",
        scenario_run_id=run_id,
        atc_link_connected=connected,
        changed_at=at,
    )


def _real_agent_classes():
    try:
        from app.modules.guardian import DeterministicGuardianAgent
        from app.modules.sentinel import DeterministicSentinelAgent
    except ImportError:
        pytest.skip("current archive lacks merged deterministic Guardian/Sentinel; run on updated Mac checkout")
    return DeterministicGuardianAgent, DeterministicSentinelAgent


def test_default_composition_remains_mock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("AEROGUARD_AGENT_MODE", raising=False)
    app = create_app(tmp_path / "default.db")
    with TestClient(app) as client:
        assert app.state.agent_mode == "mock"
        assert type(app.state.orchestrator.guardian).__name__ == "MockGuardianAgent"
        assert type(app.state.orchestrator.sentinel).__name__ == "MockSentinelAgent"
        assert client.get("/healthz").json() == {"status": "ok", "simulation_only": True}


def test_explicit_mock_preserves_demo_even_if_environment_uses_mock(tmp_path: Path):
    app = create_app(tmp_path / "explicit-mock.db", agent_mode="mock")
    with TestClient(app) as client:
        assert app.state.agent_mode == "mock"
        started = _start(client, "dual_pilot_atc_connected")
        run_id = started["scenario_run_id"]
        snapshot = _advance(client, run_id, 2000)
        assert snapshot["active_incident"] is not None
        assert snapshot["sentinel_state"] == "AWAITING_ATC"


@pytest.mark.parametrize("mode", ["", "live", "MOCK", "real", "deterministic "])
def test_invalid_agent_mode_rejected(tmp_path: Path, mode: str):
    with pytest.raises(ValueError, match="agent_mode"):
        create_app(tmp_path / "invalid.db", agent_mode=mode)


def test_invalid_environment_mode_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("AEROGUARD_AGENT_MODE", "production")
    with pytest.raises(ValueError, match="AEROGUARD_AGENT_MODE"):
        create_app(tmp_path / "invalid-env.db")


def test_explicit_mock_override_invalid_environment_still_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # Validate external configuration; silently accepting typoed modes is unsafe.
    monkeypatch.setenv("AEROGUARD_AGENT_MODE", "unexpected")
    with pytest.raises(ValueError, match="AEROGUARD_AGENT_MODE"):
        create_app(tmp_path / "invalid-override.db", agent_mode="mock")


def test_environment_can_opt_in_and_explicit_mock_can_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    Guardian, Sentinel = _real_agent_classes()
    monkeypatch.setenv("AEROGUARD_AGENT_MODE", "deterministic")
    active = create_app(tmp_path / "env-real.db")
    fallback = create_app(tmp_path / "env-mock.db", agent_mode="mock")
    try:
        assert active.state.agent_mode == "deterministic"
        assert isinstance(active.state.orchestrator.guardian, Guardian)
        assert isinstance(active.state.orchestrator.sentinel, Sentinel)
        assert fallback.state.agent_mode == "mock"
        assert type(fallback.state.orchestrator.guardian).__name__ == "MockGuardianAgent"
        assert type(fallback.state.orchestrator.sentinel).__name__ == "MockSentinelAgent"
    finally:
        active.state.orchestrator.close()
        fallback.state.orchestrator.close()


def test_real_and_mock_modes_share_exact_openapi_contract(tmp_path: Path):
    _real_agent_classes()
    mock = create_app(tmp_path / "schema-mock.db", agent_mode="mock")
    real = create_app(tmp_path / "schema-real.db", agent_mode="deterministic")
    try:
        assert mock.openapi() == real.openapi()
        assert mock.state.agent_mode == "mock"
        assert real.state.agent_mode == "deterministic"
    finally:
        mock.state.orchestrator.close()
        real.state.orchestrator.close()


@pytest.mark.parametrize(
    "scenario,expect_incident,expect_status",
    [
        ("normal_flight", False, "NORMAL"),
        ("single_pilot_unresponsive", False, None),
        ("camera_obstructed", False, None),
        ("dual_pilot_atc_connected", True, "ESCALATED"),
        ("dual_pilot_atc_disconnected", True, "ESCALATED"),
    ],
)
def test_real_agents_five_canonical_scenarios_are_non_authorizing_without_approval(
    tmp_path: Path, scenario: str, expect_incident: bool, expect_status: str | None
):
    _real_agent_classes()
    with _client(tmp_path) as client:
        run_id = _start(client, scenario)["scenario_run_id"]
        snapshot = _advance(client, run_id, 2000)
        assert (snapshot["active_incident"] is not None) == expect_incident
        assert snapshot["last_simulator_action"] is None
        if expect_status:
            assert snapshot["guardian_state"] == expect_status
        if scenario == "single_pilot_unresponsive":
            assert any(
                pilot["latest_observation"]["observation_status"] == "RESPONSIVE"
                for pilot in snapshot["pilots"]
            )
        if scenario == "camera_obstructed":
            assert all(
                pilot["latest_observation"]["observation_status"] == "UNKNOWN"
                for pilot in snapshot["pilots"]
            )
        assert snapshot["sentinel_state"] == (
            "AWAITING_ATC" if scenario == "dual_pilot_atc_connected" else "STANDBY"
        )
        assert not any(
            item["event_type"] == "SIMULATOR_ACTION"
            for item in client.get("/api/v1/events", params={"limit": 100}).json()["events"]
        )


@pytest.mark.parametrize("batch", [False, True])
def test_real_guardian_escalates_equivalently_for_batch_and_split_advances(
    tmp_path: Path, batch: bool
):
    _real_agent_classes()
    with _client(tmp_path) as client:
        run_id, incident, snapshot = _incident(client, batch=batch)
        assert incident["incident_type"] == "DUAL_PILOT_UNRESPONSIVE"
        assert snapshot["sentinel_state"] == "AWAITING_ATC"
        events = client.get("/api/v1/events", params={"limit": 100}).json()["events"]
        observed = [
            datetime.fromisoformat(item["occurred_at"])
            for item in events if item["event_type"] == "PILOT_OBSERVATION"
        ]
        assert len(observed) == 4
        assert observed[0] == observed[1]
        assert observed[2] == observed[3]
        assert observed[2] - observed[0] == timedelta(seconds=1)
        assert incident["created_at"] == events[
            next(i for i, item in enumerate(events) if item["event_type"] == "GUARDIAN_INCIDENT")
        ]["payload"]["created_at"]


def test_real_agents_reject_then_authorize_once_and_replay_is_idempotent(tmp_path: Path):
    _real_agent_classes()
    with _client(tmp_path) as client:
        run_id, incident, snapshot = _incident(client)
        rejected, _ = _atc(
            client, run_id, incident["incident_id"], snapshot["virtual_time"], decision="REJECT"
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["snapshot"]["last_simulator_action"] is None
        approved, approval_body = _atc(
            client, run_id, incident["incident_id"], snapshot["virtual_time"]
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["snapshot"]["last_simulator_action"]["action_type"] == "SIM_STABILIZE"
        duplicate = client.post("/api/v1/atc/decision", json=approval_body)
        assert duplicate.status_code == 200, duplicate.text
        assert duplicate.json()["duplicate"] is True
        conflicting = dict(approval_body, operator_id="conflicting-atc")
        conflict_response = client.post("/api/v1/atc/decision", json=conflicting)
        assert conflict_response.status_code == 409
        assert conflict_response.json()["code"] == "COMMAND_ID_CONFLICT"
        assert sum(
            ev["event_type"] == "SIMULATOR_ACTION"
            for ev in client.get("/api/v1/events", params={"limit": 100}).json()["events"]
        ) == 1


def test_real_agents_disconnected_escalation_reconnect_waits_for_atc(tmp_path: Path):
    _real_agent_classes()
    with _client(tmp_path) as client:
        run_id, incident, snapshot = _incident(client, "dual_pilot_atc_disconnected")
        assert snapshot["sentinel_state"] == "STANDBY"
        response = _link(client, run_id, True, snapshot["virtual_time"])
        assert response.status_code == 200, response.text
        assert response.json()["snapshot"]["last_simulator_action"] is None
        assert response.json()["snapshot"]["sentinel_state"] == "AWAITING_ATC"
        approved, _ = _atc(
            client, run_id, incident["incident_id"], snapshot["virtual_time"]
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["snapshot"]["last_simulator_action"] is not None


def test_real_agents_acknowledgement_revokes_pending_api_authorization(tmp_path: Path):
    _real_agent_classes()
    with _client(tmp_path) as client:
        run_id, incident, snapshot = _incident(client)
        response = _post(
            client,
            "/api/v1/pilots/acknowledge",
            scenario_run_id=run_id,
            pilot_id="PILOT_1",
            alert_id=incident["incident_id"],
            acknowledged_at=snapshot["virtual_time"],
        )
        assert response.status_code == 200, response.text
        assert response.json()["snapshot"]["active_incident"] is None
        blocked, _ = _atc(client, run_id, incident["incident_id"], snapshot["virtual_time"])
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "NO_ACTIVE_INCIDENT"
        assert client.get("/api/v1/state").json()["last_simulator_action"] is None


def test_real_agents_reset_protects_new_run_and_old_incident(tmp_path: Path):
    _real_agent_classes()
    with _client(tmp_path) as client:
        run_id, incident, snapshot = _incident(client)
        reset = _post(client, "/api/v1/scenarios/reset", scenario_run_id=run_id)
        assert reset.status_code == 200, reset.text
        new_run = reset.json()["snapshot"]["scenario_run_id"]
        assert new_run != run_id
        assert reset.json()["snapshot"]["active_incident"] is None
        blocked, _ = _atc(client, run_id, incident["incident_id"], snapshot["virtual_time"])
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "STALE_SCENARIO_RUN"
        new_snapshot = _advance(client, new_run, 2000)
        assert new_snapshot["guardian_state"] == "ESCALATED"
        assert new_snapshot["active_incident"]["incident_id"] != incident["incident_id"]


def test_real_agents_wrong_incident_rejected_without_simulator_action(tmp_path: Path):
    _real_agent_classes()
    with _client(tmp_path) as client:
        run_id, _, snapshot = _incident(client)
        blocked, _ = _atc(client, run_id, str(uuid4()), snapshot["virtual_time"])
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "INCIDENT_MISMATCH"
        assert client.get("/api/v1/state").json()["last_simulator_action"] is None
