"""Platform authorization regressions. SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.contracts.enums import GuardianState, PilotId, PilotObservationStatus
from app.contracts.models import PilotObservation
from app.main import create_app
from app.modules.guardian.mock import MockGuardianAgent


class RecoverOnResponsiveEvidence(MockGuardianAgent):
    """Minimal test double for the real Guardian's observation-driven recovery."""

    def consume_observation(self, event):
        emitted = super().consume_observation(event)
        if event.payload.observation_status == PilotObservationStatus.RESPONSIVE:
            self._active_incident = None
            self._state = GuardianState.RECOVERING
        return emitted


class ResponsiveVision:
    def configure_scenario(self, scenario_id: str) -> None:
        self.scenario_id = scenario_id

    def observe(self, pilot_id, observed_at):
        return PilotObservation(
            pilot_id=pilot_id,
            observed_at=observed_at,
            observation_status=PilotObservationStatus.RESPONSIVE,
            camera_available=True,
            face_visible=True,
            eyes_closed=False,
            observation_duration_ms=1_000,
            observation_quality=0.95,
        )


def _start_and_escalate(client: TestClient):
    start = client.post("/api/v1/scenarios/start", json={
        "command_id": str(uuid4()), "scenario_id": "dual_pilot_atc_connected",
    })
    assert start.status_code == 200, start.text
    run_id = start.json()["snapshot"]["scenario_run_id"]
    for _ in range(2):
        advance = client.post("/api/v1/scenarios/advance", json={
            "command_id": str(uuid4()), "scenario_run_id": run_id, "delta_ms": 1000,
        })
        assert advance.status_code == 200, advance.text
    incident = advance.json()["snapshot"]["active_incident"]
    assert incident is not None
    return run_id, incident["incident_id"]


def _approval(client: TestClient, run_id: str, incident_id: str):
    return client.post("/api/v1/atc/decision", json={
        "command_id": str(uuid4()),
        "scenario_run_id": run_id,
        "incident_id": incident_id,
        "decision": "APPROVE",
        "requested_action": "SIM_STABILIZE",
        "operator_id": "synthetic-atc",
        "issued_at": datetime.now(timezone.utc).isoformat(),
    })


def _assert_no_execution(client: TestClient):
    events = client.get("/api/v1/events", params={"after_seq": 0, "limit": 100}).json()["events"]
    assert not any(event["event_type"] == "SIMULATOR_ACTION" for event in events)
    assert client.get("/api/v1/state").json()["last_simulator_action"] is None


def test_responsive_recovery_clears_snapshot_and_blocks_stale_approval(tmp_path):
    app = create_app(tmp_path / "recovery.db")
    orchestrator = app.state.orchestrator
    orchestrator.guardian = RecoverOnResponsiveEvidence()
    with TestClient(app) as client:
        run_id, incident_id = _start_and_escalate(client)
        assert orchestrator.guardian.active_incident is not None
        assert orchestrator._runner is not None
        orchestrator._runner.advance = lambda _: [PilotId.PILOT_1, PilotId.PILOT_2]
        orchestrator.vision = ResponsiveVision()
        response = client.post("/api/v1/scenarios/advance", json={
            "command_id": str(uuid4()), "scenario_run_id": run_id, "delta_ms": 1000,
        })
        assert response.status_code == 200, response.text
        assert orchestrator.guardian.active_incident is None
        assert response.json()["snapshot"]["guardian_state"] == "RECOVERING"
        assert response.json()["snapshot"]["active_incident"] is None
        rejection = _approval(client, run_id, incident_id)
        assert rejection.status_code == 409, rejection.text
        assert rejection.json()["code"] == "NO_ACTIVE_INCIDENT"
        _assert_no_execution(client)


def test_authority_gate_catches_recovery_even_before_snapshot_refresh(tmp_path):
    app = create_app(tmp_path / "authority.db")
    with TestClient(app) as client:
        run_id, incident_id = _start_and_escalate(client)
        guardian = app.state.orchestrator.guardian
        # Simulate an asynchronous observation-driven Guardian retirement between API calls.
        guardian._active_incident = None
        guardian._state = GuardianState.RECOVERING
        assert client.get("/api/v1/state").json()["active_incident"] is not None
        rejection = _approval(client, run_id, incident_id)
        assert rejection.status_code == 409, rejection.text
        assert rejection.json()["code"] == "NO_ACTIVE_INCIDENT"
        _assert_no_execution(client)


def test_incident_identity_change_blocks_approval_without_sentinel_handoff(tmp_path):
    app = create_app(tmp_path / "identity.db")
    with TestClient(app) as client:
        run_id, incident_id = _start_and_escalate(client)
        guardian = app.state.orchestrator.guardian
        guardian._active_incident = guardian.active_incident.model_copy(
            update={"incident_id": uuid4()},
        )
        rejection = _approval(client, run_id, incident_id)
        assert rejection.status_code == 409, rejection.text
        assert rejection.json()["code"] == "INCIDENT_NOT_SYNCHRONIZED"
        _assert_no_execution(client)


def test_acknowledgement_prevents_any_later_approval(tmp_path):
    app = create_app(tmp_path / "ack.db")
    with TestClient(app) as client:
        run_id, incident_id = _start_and_escalate(client)
        ack = client.post("/api/v1/pilots/acknowledge", json={
            "command_id": str(uuid4()), "scenario_run_id": run_id,
            "pilot_id": "PILOT_1", "alert_id": incident_id,
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
        })
        assert ack.status_code == 200, ack.text
        rejection = _approval(client, run_id, incident_id)
        assert rejection.status_code == 409, rejection.text
        assert rejection.json()["code"] == "NO_ACTIVE_INCIDENT"
        _assert_no_execution(client)


def test_real_guardian_and_sentinel_recovery_rejects_stale_atc(tmp_path):
    """Full agent pair once the already-merged main modules are available."""
    import pytest

    try:
        from app.modules.guardian import DeterministicGuardianAgent
        from app.modules.sentinel import DeterministicSentinelAgent
    except ImportError:
        pytest.skip("deterministic Guardian/Sentinel modules are not in the P0 source archive")

    app = create_app(tmp_path / "real-pair.db")
    orchestrator = app.state.orchestrator
    orchestrator.guardian = DeterministicGuardianAgent()
    orchestrator.sentinel = DeterministicSentinelAgent()
    with TestClient(app) as client:
        run_id, incident_id = _start_and_escalate(client)
        assert orchestrator.guardian.active_incident is not None
        assert orchestrator._runner is not None
        orchestrator._runner.advance = lambda _: [PilotId.PILOT_1, PilotId.PILOT_2]
        orchestrator.vision = ResponsiveVision()
        for _ in range(2):
            advance = client.post("/api/v1/scenarios/advance", json={
                "command_id": str(uuid4()), "scenario_run_id": run_id, "delta_ms": 1000,
            })
            assert advance.status_code == 200, advance.text
        assert orchestrator.guardian.active_incident is None
        assert advance.json()["snapshot"]["active_incident"] is None
        approval = _approval(client, run_id, incident_id)
        assert approval.status_code == 409, approval.text
        assert approval.json()["code"] == "NO_ACTIVE_INCIDENT"
        _assert_no_execution(client)
