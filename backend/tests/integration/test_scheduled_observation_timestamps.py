"""Scheduled observation timing regressions. SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _execute(client: TestClient, scenario_id: str, advances: tuple[int, ...]):
    start = client.post("/api/v1/scenarios/start", json={
        "command_id": str(uuid4()), "scenario_id": scenario_id,
    })
    assert start.status_code == 200, start.text
    run_id = start.json()["snapshot"]["scenario_run_id"]
    result = None
    for delta_ms in advances:
        result = client.post("/api/v1/scenarios/advance", json={
            "command_id": str(uuid4()), "scenario_run_id": run_id, "delta_ms": delta_ms,
        })
        assert result.status_code == 200, result.text
    assert result is not None
    history = client.get("/api/v1/events", params={"after_seq": 0, "limit": 100})
    assert history.status_code == 200, history.text
    observations = [event for event in history.json()["events"]
                    if event["scenario_run_id"] == run_id and event["event_type"] == "PILOT_OBSERVATION"]
    return result.json()["snapshot"], observations, run_id


def _expect_timestamps(observations):
    assert len(observations) == 4
    expected = [BASE + timedelta(seconds=1)] * 2 + [BASE + timedelta(seconds=2)] * 2
    assert [datetime.fromisoformat(event["occurred_at"]) for event in observations] == expected
    assert [datetime.fromisoformat(event["payload"]["observed_at"]) for event in observations] == expected
    assert [event["payload"]["pilot_id"] for event in observations] == [
        "PILOT_1", "PILOT_2", "PILOT_1", "PILOT_2",
    ]
    assert len({event["event_id"] for event in observations}) == 4


@pytest.mark.parametrize("scenario_id", [
    "normal_flight", "single_pilot_unresponsive", "dual_pilot_atc_connected",
    "dual_pilot_atc_disconnected", "camera_obstructed",
])
def test_large_and_split_advances_preserve_observation_instants(tmp_path, scenario_id):
    outcomes = []
    for label, advances in (("one", (2_000,)), ("split", (1_000, 1_000)),
                            ("mixed", (500, 1_500))):
        app = create_app(tmp_path / f"{scenario_id}-{label}.db")
        with TestClient(app) as client:
            snapshot, observations, run_id = _execute(client, scenario_id, advances)
            _expect_timestamps(observations)
            assert snapshot["scenario_run_id"] == run_id
            assert datetime.fromisoformat(snapshot["virtual_time"]) == BASE + timedelta(seconds=2)
            assert all(datetime.fromisoformat(p["latest_observation"]["observed_at"]) ==
                       BASE + timedelta(seconds=2) for p in snapshot["pilots"])
            assert snapshot["last_simulator_action"] is None
            outcomes.append((snapshot["guardian_state"], snapshot["sentinel_state"],
                             [p["latest_observation"]["observation_status"] for p in snapshot["pilots"]]))
    assert outcomes[0] == outcomes[1] == outcomes[2]


def test_repeated_large_advances_do_not_reemit_scheduled_observations(tmp_path):
    app = create_app(tmp_path / "no-reemit.db")
    with TestClient(app) as client:
        snapshot, observations, run_id = _execute(client, "dual_pilot_atc_connected", (2_000, 10_000))
        _expect_timestamps(observations)
        assert datetime.fromisoformat(snapshot["virtual_time"]) == BASE + timedelta(seconds=12)
        assert snapshot["last_simulator_action"] is None
        # Reusing a command id is still controlled by command record semantics.
        assert run_id == snapshot["scenario_run_id"]


@pytest.mark.parametrize("scenario_id", ["dual_pilot_atc_connected", "dual_pilot_atc_disconnected"])
def test_real_guardian_batch_parity_and_no_automatic_action(tmp_path, scenario_id):
    try:
        from app.modules.guardian import DeterministicGuardianAgent
        from app.modules.sentinel import DeterministicSentinelAgent
    except ImportError:
        pytest.skip("real Guardian and Sentinel are not present in the source archive")

    incident_snapshots = []
    for label, advances in (("one", (2_000,)), ("split", (1_000, 1_000))):
        app = create_app(tmp_path / f"real-{scenario_id}-{label}.db")
        orchestrator = app.state.orchestrator
        orchestrator.guardian = DeterministicGuardianAgent()
        orchestrator.sentinel = DeterministicSentinelAgent()
        with TestClient(app) as client:
            snapshot, observations, _ = _execute(client, scenario_id, advances)
            _expect_timestamps(observations)
            incident = snapshot["active_incident"]
            assert incident is not None, f"{scenario_id}: Guardian must escalate with {advances}"
            assert len(incident["evidence_event_ids"]) == 4
            assert datetime.fromisoformat(incident["created_at"]) == BASE + timedelta(seconds=2)
            assert snapshot["guardian_state"] == "ESCALATED"
            assert snapshot["sentinel_state"] == (
                "AWAITING_ATC" if scenario_id == "dual_pilot_atc_connected" else "STANDBY"
            )
            assert snapshot["last_simulator_action"] is None
            incident_snapshots.append((incident["incident_type"], snapshot["guardian_state"],
                                       snapshot["sentinel_state"]))
    assert incident_snapshots[0] == incident_snapshots[1]
