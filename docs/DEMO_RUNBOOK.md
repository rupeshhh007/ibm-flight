# AeroGuard Demo Runbook

> **SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE**

## Status

The six-member local application, including React dashboard and integrated backend, is merged into `main` as of October 18, 2026. The final pre-merge combination passed 690 backend tests (10 skipped), 69 frontend tests, and an 18-event safety smoke test. Re-run on final `main` before reporting final-main results. IBM LinuxONE deployment and replay-safe SSE remain unverified/not shipped.

## Environment preparation

Prerequisites are Python 3.11+, Node.js/npm, GNU Make, Git, and SQLite support. For a fresh checkout, use:

```text
make setup
make check
make smoke
npm --prefix frontend test
npm --prefix frontend run build
```

Start `AEROGUARD_AGENT_MODE=deterministic make backend` in the first terminal (or `make backend` for default mocks). Start `npm --prefix frontend run dev` in a second terminal, then open `http://127.0.0.1:5173/`. The backend listens on `127.0.0.1:8000`. The default mock path requires no webcam, LinuxONE, or credentials. Confirm `/healthz`, `/readyz`, `/api/v1/state`, and `/api/v1/scenarios`. If Vite reports `ECONNREFUSED 127.0.0.1:8000`, the backend is not running.

## Common scenario procedure

1. Select the stable scenario ID in the **Scenarios** view, or use generated OpenAPI at `/docs`.
2. Start the scenario through `POST /api/v1/scenarios/start`. Record the returned `scenario_run_id`; the first committed events have increasing `seq` values.
3. Query `GET /api/v1/state` and confirm both pilot entries, synthetic telemetry, Guardian/Sentinel states, and the simulation-only status.
4. Advance virtual time in bounded steps. Boundary events are expected to be inclusive; do not wait real minutes.
5. Observe the audit timeline after each step and correlate incident evidence event IDs.
6. Use `POST /api/v1/atc/decision` only for the connected dual-pilot scenario; the fictional ATC screen is P1.
7. Reset from the active run. Confirm a new run identity, initial state, retained old history, and rejection of any old-run command.

The request/response bodies are implemented Pydantic models and are available in live OpenAPI and `docs/CONTRACTS.md`. `make smoke` executes the complete connected path without manual database edits.

## Scenario 1: `normal_flight`

### P0 verified behavior

- Both pilot observations remain `RESPONSIVE`; telemetry is nominal and synthetic.
- Guardian remains `NORMAL`; no active incident is produced.
- Sentinel remains `STANDBY`; no simulator action occurs.
- Timeline shows start, deterministic advances, observations/telemetry, then completion as scripted.

### Presentation point

Establish that the platform does not manufacture emergencies from normal data and that virtual time drives a repeatable audit trail.

## Scenario 2: `single_pilot_unresponsive`

### P0 verified behavior

- One pilot receives repeated scripted concern observations while the other remains responsive.
- Guardian may move through `SUSPECTED`/`AWAITING_ACK` and request acknowledgement.
- Submit a valid acknowledgement if the scenario schedules it; recovery follows the documented rule.
- A responsive second pilot prevents a dual-pilot conclusion.
- Sentinel requests no autonomous action; simulator action remains absent.

### Presentation point

Show conservative evidence fusion: one uncertain pilot does not equal aircraft takeover.

## Scenario 3: `dual_pilot_atc_connected`

### P0 verified behavior

1. Advance until combined current-run evidence and missed acknowledgements create a Guardian escalation.
2. Sentinel enters `AWAITING_ATC`; verify no action exists before an ATC decision.
3. Demonstrate a simulated `REJECT` or explain the negative test: it records rejection and performs no action.
4. If restarting/resetting the scenario for the approval path, use the new run/incident IDs.
5. Submit `APPROVE` for the active incident/run and one allowed symbolic action.
6. Sentinel records authorization; the simulator independently validates and executes at most once.
7. Replay the same command: no second action may occur.

### Presentation point

The fictional ATC console is not real authentication. Its value is proving explicit, referential authorization and idempotency.

## Scenario 4: `dual_pilot_atc_disconnected`

### P0 verified negative behavior; positive offline fallback is P1

1. Show that toggling simulated ATC to disconnected produces no action by itself.
2. Advance the scripted scenario until stronger evidence includes both pilots, missed acknowledgements, an active escalation, and the current-run safety condition.
3. Sentinel may enter `LOCAL_FALLBACK` and select only the documented restricted symbolic fallback.
4. The simulator independently validates the action and active run; one auditable result follows.
5. Removing any prerequisite in negative tests prevents fallback.

### Presentation point

Disconnected mode is a constrained scripted demonstration, not an autopilot or real emergency-navigation capability.

## Scenario 5: `camera_obstructed`

### P0 verified behavior

- Camera unavailable/obstructed or face not visible yields `UNKNOWN` with reduced/appropriate quality.
- Guardian does not upgrade obstruction into `POSSIBLY_UNRESPONSIVE`.
- No incident/action follows from camera obstruction alone.
- Telemetry and the rest of the local system continue operating.

### Presentation point

Emphasize that the vision component reports uncertainty rather than a medical diagnosis.

## Reset and audit checks

After every scenario, capture the last sequence and old run ID, reset, and verify:

- the active run ID changes;
- Guardian/Sentinel/simulator state returns to documented initial values;
- old events remain available through history;
- sequence numbers continue increasing globally;
- an old-run acknowledgement or ATC decision is rejected and causes no action.

## Capture evidence

Record the current `git rev-parse HEAD` and completed command outputs. Capture screenshots of **Flight Deck**, **Scenarios**, **Sentinel** (before and after fictional approval), and **Black Box** (ordered event history). Make a short video showing connected-dual-pilot escalation, rejection with no simulator action, subsequent valid approval with one `SIM_STABILIZE`, and deduplication. Verify `normal_flight` and `camera_obstructed` remain safe. Do not show LinuxONE as deployed without a real target/ingestion record.

## Suggested judge sequence

1. Safety banner, architecture, and synthetic-only boundary.
2. `normal_flight` for deterministic telemetry/audit.
3. `camera_obstructed` for uncertainty handling.
4. `single_pilot_unresponsive` for conservative Guardian behavior.
5. Connected dual-pilot path: wait, reject/no action, then valid approval/one action.
6. Disconnected path: toggle/no action, then prerequisite-gated fallback.
7. Reset/old-run rejection and event replay.
8. Optional LinuxONE supervisory concept only if actual verified evidence exists.

## Troubleshooting

| Symptom | Check | Safe response |
|---|---|---|
| Readiness fails | SQLite/config/startup diagnostics | Use documented local config; do not bypass validation |
| UI cannot reach API | Vite proxy and printed addresses | Avoid hardcoded host changes during demo |
| Timeline misses events | REST history after last `seq` | Fall back to polling; do not claim SSE correctness |
| Stale command rejected | Compare active run/incident IDs | Refresh snapshot and submit a new command ID |
| Optional webcam fails | Optional dependency/device permissions | Switch to deterministic mock adapter |
| Remote sync fails | Separate sync status/pending count | Continue local demo; LinuxONE is non-critical |
| Unexpected action | Stop advancing, preserve logs/DB | Treat as a release blocker; do not continue presentation as safe |

Before the actual demo, record verified commands and observed outcomes here. Never convert expected behavior into a passed claim without test or rehearsal evidence.
