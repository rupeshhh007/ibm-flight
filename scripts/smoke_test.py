from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


def require_ok(response, label: str) -> dict:
    if response.status_code != 200:
        raise RuntimeError(f"{label} failed: {response.status_code} {response.text}")
    return response.json()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aeroguard-smoke-") as directory:
        app = create_app(Path(directory) / "smoke.db")
        with TestClient(app) as client:
            require_ok(client.get("/healthz"), "health")
            started = require_ok(
                client.post(
                    "/api/v1/scenarios/start",
                    json={"command_id": str(uuid4()), "scenario_id": "dual_pilot_atc_connected"},
                ),
                "scenario start",
            )
            run_id = started["snapshot"]["scenario_run_id"]
            for _ in range(2):
                advanced = require_ok(
                    client.post(
                        "/api/v1/scenarios/advance",
                        json={"command_id": str(uuid4()), "scenario_run_id": run_id, "delta_ms": 1_000},
                    ),
                    "scenario advance",
                )
            incident_id = advanced["snapshot"]["active_incident"]["incident_id"]
            assert advanced["snapshot"]["sentinel_state"] == "AWAITING_ATC"
            assert advanced["snapshot"]["last_simulator_action"] is None
            rejected = require_ok(
                client.post(
                    "/api/v1/atc/decision",
                    json={
                        "command_id": str(uuid4()),
                        "scenario_run_id": run_id,
                        "incident_id": incident_id,
                        "decision": "REJECT",
                        "requested_action": "SIM_STABILIZE",
                        "operator_id": "fictional-atc-smoke",
                        "issued_at": datetime.now(timezone.utc).isoformat(),
                    },
                ),
                "ATC rejection",
            )
            assert rejected["snapshot"]["last_simulator_action"] is None
            approval_command = str(uuid4())
            approval = {
                "command_id": approval_command,
                "scenario_run_id": run_id,
                "incident_id": incident_id,
                "decision": "APPROVE",
                "requested_action": "SIM_STABILIZE",
                "operator_id": "fictional-atc-smoke",
                "issued_at": datetime.now(timezone.utc).isoformat(),
            }
            approved = require_ok(client.post("/api/v1/atc/decision", json=approval), "ATC approval")
            duplicate = require_ok(client.post("/api/v1/atc/decision", json=approval), "duplicate approval")
            assert approved["snapshot"]["last_simulator_action"]["action_type"] == "SIM_STABILIZE"
            assert duplicate["duplicate"] is True
            history = require_ok(client.get("/api/v1/events?after_seq=0&limit=100"), "event history")
            action_events = [event for event in history["events"] if event["event_type"] == "SIMULATOR_ACTION"]
            assert len(action_events) == 1
            print(
                "SMOKE PASS: start -> deterministic advances -> Guardian incident -> Sentinel wait -> "
                "ATC reject/no action -> ATC approve -> exactly one SIM_STABILIZE -> duplicate suppressed"
            )
            print(f"SMOKE EVENTS: {len(history['events'])}; latest_seq={history['latest_event_seq']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
