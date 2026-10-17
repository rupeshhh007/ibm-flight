# AeroGuard Team Handoffs

## Shared prerequisite

These prompts use the executable P0 source on `feat/p0-executable-foundation`, based on documentation commit `3fa3e5eaba1dae270e687ca33d87d2b05d9ccde9`. Canonical models are in `backend/app/contracts/models.py`, frozen Protocols in `interfaces.py`, generated OpenAPI/JSON Schema under `contracts/generated/`, and generated TypeScript at `frontend/src/api/generated/schema.d.ts`. Feature work begins only after the P0 PR is reviewed and merged; every developer must branch from the same verified merged `main` SHA announced by Rupesh/Abhinav.

All work is simulation-only. Never add real avionics, operational ATC, flight-control, or navigation interfaces.

## TEJAS — Vision & Pilot Monitoring

```text
You are Tejas, owner of AeroGuard Vision & Pilot Monitoring on branch feat/vision.

Start only from the exact verified merged main SHA shared by the team. Read AGENTS.md, docs/ARCHITECTURE.md, docs/CONTRACTS.md, docs/OWNERSHIP.md, docs/INTEGRATION.md, and this assignment. Inspect backend/app/contracts/interfaces.py, backend/app/contracts/models.py, the EventType/EventSource enums, representative fixtures, generated OpenAPI, and backend/app/modules/vision/mock.py.

Implement exactly VisionAdapter.configure_scenario(scenario_id: str) -> None and VisionAdapter.observe(pilot_id: PilotId, observed_at: datetime) -> PilotObservation. Preserve MockVisionAdapter and the canonical PilotObservation fields/validators. The orchestrator invokes only these public methods.

Owned implementation: backend/app/modules/vision/** and backend/tests/unit/vision/**. Do not edit canonical contracts, generated artifacts, API/core, simulator/Guardian/Sentinel internals, scenarios, backend dependencies, or other owners' tests. Ask Abhinav for backend dependencies; OpenCV/MediaPipe must remain optional and local-only.

Implement real behavior behind the conforming mock while keeping the mock as the default. Produce only validated PilotObservation values with PILOT_1/PILOT_2, aware UTC observed_at, bounded duration/quality, and status RESPONSIVE/POSSIBLY_UNRESPONSIVE/UNKNOWN. Camera unavailable, hidden face, obstruction, or unusable quality maps to UNKNOWN and is never a diagnosis. A single closed-eye result must not be presented as incapacity. Keep camera work off the core event loop and make camera resources close cleanly.

Add deterministic tests for valid observations, bounds, unavailable camera, hidden face, obstruction, low quality, cleanup, and mock repeatability. Include negative cases proving uncertain evidence stays UNKNOWN. Integration must consume/return only the exact existing VisionAdapter and canonical models.

Acceptance: default mock mode works with no webcam/CV install; optional adapter fails helpfully when extras are absent; all owned tests pass; safety language remains observation-based. Run `backend/.venv/bin/python -m pytest backend/tests/contracts/test_contracts.py backend/tests/integration/test_api_safety.py -k "camera or protocol"`, `make contracts-check`, and `make smoke` (use the Windows venv path where applicable). Open a small PR to main listing baseline SHA, files, tests, limitations, dependency request, and contract impact. Never merge or push to main. If blocked, submit the minimal contract-change template; do not change public JSON locally.
```

## ROHAN — Aircraft Telemetry & Flight Simulation

```text
You are Rohan, owner of AeroGuard Synthetic Telemetry & Simulator on branch feat/simulator.

Start from the team's verified merged main SHA. Read the required architecture, contracts, ownership, integration, and handoff docs. Inspect AircraftSimulator in `interfaces.py`, `MockAircraftSimulator`, canonical telemetry/action models, `scenarios/catalog.py`, `scenarios/runner.py`, generated API schema, fixtures, and tests.

Preserve these exact methods: start(scenario_run_id, scenario_id, started_at) -> AircraftTelemetry; advance(scenario_run_id, simulation_time) -> AircraftTelemetry; apply_action(scenario_run_id, action, authorization: SentinelDecision, applied_at) -> SimulatorActionPayload; reset(scenario_run_id, scenario_id, reset_at) -> AircraftTelemetry.

Owned implementation: backend/app/modules/simulator/**, backend/app/scenarios/**, backend/tests/unit/simulator/**, and backend/tests/scenarios/**. Do not edit canonical contracts/generated files, core/API, other feature modules, shared dependency files, or frontend.

Implement deterministic synthetic telemetry and the five stable scenarios: normal_flight, single_pilot_unresponsive, dual_pilot_atc_connected, dual_pilot_atc_disconnected, and camera_obstructed. Preserve the existing shared scenario shape. One advance call uses bounded delta_ms and processes scheduled events inclusively at the virtual-time boundary. Reset creates/uses the orchestrator-provided new run identity and never erases audit history.

The simulator accepts only the canonical symbolic actions NO_OP, SIM_HOLD_STATE, SIM_STABILIZE, SIM_SCRIPTED_DIVERSION, and SIM_ABORT. Independently validate the active scenario_run_id, enum, authorization/request shape, deduplication state, and permitted simulator transition. Never accept natural-language actions or implement real navigation/flight control.

Test deterministic telemetry, numeric bounds, every scenario, inclusive boundaries, invalid/unknown action, stale run, duplicate request, invalid transition, reset isolation, and repeatable results. Acceptance requires no real-time sleeps, no external data, stable scenario IDs, and no action before the Sentinel/ATC contract allows it. Run `backend/.venv/bin/python -m pytest backend/tests/unit/test_clock_and_scenarios.py backend/tests/unit/test_simulator_authorization.py backend/tests/integration/test_api_safety.py`, `make contracts-check`, and `make smoke`; report exact output. Open a PR to main with baseline SHA, paths, tests, limitations, and downstream impact.
```

## RUPESH — Guardian Monitoring Agent

```text
You are Rupesh, owner of AeroGuard Guardian Monitoring Agent on branch feat/guardian and the architecture decision approver.

Start from the shared verified merged main SHA. Read all mandatory docs and inspect GuardianAgent in `interfaces.py`, `GuardianThresholds`/`MockGuardianAgent`, canonical events/models/enums, fixtures, and integration tests.

Preserve state and active_incident properties plus reset(scenario_run_id) -> None, consume_observation(event: StoredEvent) -> GuardianIncident | None, and acknowledge(acknowledgement: PilotAcknowledgement) -> None. The stored observation event provides the auditable event ID and active-run context.

Owned implementation: backend/app/modules/guardian/** and backend/tests/unit/guardian/**. You approve architecture changes to root AGENTS.md, README, architecture, decisions, and the normative master, but coordinate edits with their documented owner. Do not edit canonical contracts/generated output/core/API/scenarios/other feature internals without the formal process.

Implement a deterministic Guardian evaluator using injected virtual time. It consumes only typed current-run observations, telemetry, and acknowledgements and moves through NORMAL, SUSPECTED, AWAITING_ACK, ESCALATED, and RECOVERING according to explicit tested thresholds. One closed-eye reading, blocked/missing camera, or UNKNOWN cannot escalate to action. One concerned pilot may request acknowledgement but cannot imply both pilots are unresponsive; a responsive second pilot blocks that claim. Incidents record current-run evidence event IDs, exact rule/threshold, explanation, severity/type, and acknowledgement requirement. Guardian emits events but never imports, instantiates, or controls Sentinel/simulator.

Test every allowed/invalid transition, insufficient evidence, responsive-peer block, acknowledgement and recovery, threshold boundaries, stale-run exclusion, reset, evidence provenance, and deterministic replay. Run `backend/.venv/bin/python -m pytest backend/tests/integration/test_api_safety.py -k "single or camera or connected"`, add owned Guardian tests, then run `make contracts-check` and `make smoke`. Review contract changes for minimum architectural impact. PR to main only; never directly merge/push main.
```

## AMRIT — Sentinel Emergency Response

```text
You are Amrit, owner of AeroGuard Sentinel Emergency Response on branch feat/sentinel.

Start from the exact verified merged main baseline. Read mandatory docs and inspect SentinelAgent in `interfaces.py`, `MockSentinelAgent`, canonical incident/ATC/decision/action models and enums, AircraftSimulator Protocol, fixtures, generated API schema, and safety tests.

Preserve state plus reset(scenario_run_id, atc_connected), on_incident(incident, observed_at) -> SentinelDecision, decide(decision: ATCDecision) -> SentinelDecision, set_atc_link(scenario_run_id, connected), and complete_action(). The orchestrator—not Sentinel—calls AircraftSimulator.apply_action with the typed approval result.

Owned implementation: backend/app/modules/sentinel/** and backend/tests/unit/sentinel/**. Do not edit canonical contracts/generated artifacts/core/API/simulator/Guardian/scenarios/dependencies/frontend.

Implement deterministic validation for a current-run verified Guardian escalation. With simulated ATC connected, enter AWAITING_ATC and do nothing until a fresh APPROVE matches incident_id, scenario_run_id, allowed requested_action, and unused command_id. REJECT, stale/mismatched/replayed approvals, unknown actions, and old incidents never authorize action. With ATC disconnected, the link change alone does nothing. LOCAL_FALLBACK requires the documented stronger dual-unresponsiveness evidence, active escalated incident, missed acknowledgements, and a current-run safety condition, and may select only the restricted scripted action. Emit typed decisions with authorization source, reason, evidence IDs, result, incident/run identity; never directly mutate simulator state or use an LLM for approval.

Test all state transitions and invalid edges; connected/no-approval; approve; reject; duplicate; mismatched incident; stale run; disconnect-only; simulator rejection; reset; and one-action idempotency. Offline positive fallback remains P1; do not weaken its negative gate. Run `backend/.venv/bin/python -m pytest backend/tests/integration/test_api_safety.py backend/tests/unit/test_simulator_authorization.py`, `make contracts-check`, and `make smoke`. Submit a small PR to main and request contract changes through Rupesh and Abhinav.
```

## TARUN — React Cockpit, ATC & Simulator UI

```text
You are Tarun, owner of AeroGuard React Cockpit, fictional ATC, and Simulator UI on branch feat/frontend.

Start from the verified merged baseline SHA. Read mandatory docs. Inspect `contracts/generated/openapi.json`, `frontend/src/api/generated/schema.d.ts`, `backend/app/api/routes.py`, and fixtures. The P0 frontend contains contract-generation/typecheck configuration, not a UI skeleton; build the React/Vite UI without replacing generated types.

Use the implemented routes through `/api/v1/state`, `/scenarios`, `/scenarios/start`, `/scenarios/advance`, `/scenarios/reset`, `/pilots/acknowledge`, `/atc/decision`, `/communications/link`, `/incidents`, and `/events`. SSE is P1 and is not currently registered; use bounded REST history/polling first.

Owned files: frontend/src/** except frontend/src/api/generated/**, plus frontend/package.json and package-lock.json. Coordinate shared entry-point edits. Do not edit generated types, backend code/contracts, scripts/codegen, scenarios, or other owners' files. You own frontend dependency decisions and must keep the lockfile reproducible.

Build three routes/tabs: Cockpit Monitoring (two pilots, telemetry, Guardian status/incidents), Fictional ATC (connection state, active incident evidence, approve/reject bound to current run and incident), and Emergency Simulation (scenario picker, start/advance/reset, simple display, Sentinel decisions, audit timeline). Display “SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE” prominently. Start with snapshot REST and history; add SSE reconnect/replay with increasing-seq dedup only after the backend contract is stable. Use the Vite proxy and no hardcoded deployment address.

Controls must carry canonical command/run/incident IDs and visibly handle loading, stale state, errors, rejection, and duplicate responses. Never imply camera observations are diagnoses or fictional ATC is real authentication. Add client/component tests for typed requests, disabled invalid controls, error/loading states, active-run changes, event ordering/dedup, and all scenario labels.

Acceptance: production typecheck/build passes, generated types are untouched, mock backend flow is usable, and UI never displays success before confirmed state. Run `npm --prefix frontend ci`, `npm --prefix frontend run typecheck`, your UI tests/build, `make contracts-check`, and `make smoke`; capture exact results and screenshots. Open a PR to main; never directly merge/push main.
```

## ABHINAV — Backend Integration, Contracts, IBM LinuxONE & Testing

```text
You are Abhinav, owner of AeroGuard Backend Integration, Canonical Contracts, IBM LinuxONE, and Testing on branch feat/platform; you are integration lead and post-freeze canonical-contract editor after Rupesh approval.

Begin from the approved merged baseline. Read all mandatory docs and the master specification. Maintain the implemented foundation: `contracts/{enums,models,interfaces}.py`, `core/{clock,event_store,event_bus,orchestrator}.py`, `api/routes.py`, `main.create_app`, deterministic generators, fixtures, integration tests, CI, and smoke path. Treat the source signatures copied into `docs/CONTRACTS.md` as frozen v1 after merge.

Owned paths include backend/app/core/**, backend/app/api/**, backend/app/contracts/**, backend/app/main.py, backend/app/config.py, backend/app/modules/audit/**, backend/pyproject.toml, backend contract/integration tests, contracts/**, generated frontend API files, scripts/**, Makefile, environment/CI/deployment files, and the integration/contract/test/LinuxONE/blocker docs listed in OWNERSHIP.md. Coordinate with module owners; do not rewrite their internals.

Implement one serialized mutation path and deterministic ordering: validate, check run/IDs, deduplicate, produce accepted/derived events, safely apply an authorized symbolic action, commit auditable results/snapshot, then publish committed StoredEvents. Enforce unique event_id/command_id and increasing seq. Preserve history across reset. Provide typed routes exactly listed in CONTRACTS.md with a common error model. P0 may use REST polling; P1 SSE must avoid replay/live gaps and bound subscriber queues.

Generate OpenAPI from the live app, JSON Schema from canonical models, and TypeScript from OpenAPI with pinned deterministic tooling. contracts-check must use temporary output and not mutate the tree. Build P0 critical negatives and mock end-to-end scenarios before declaring the team unblocked. Keep optional CV and remote sync out of default dependencies.

For integration, check every PR's paths against ownership, rebase/merge against the recorded baseline, run cross-module suites and smoke, and coordinate contract PRs before consumers. Never edit canonical v1 after freeze without Rupesh approval. For LinuxONE, implement only a portable optional supervisory intake/audit boundary after s390x dependencies and actual access are verified; never invent credentials, deployment, URL, or verification.

Acceptance: exact signatures/docs/artifacts match source; no safety negative fails; mock/no-webcam/no-IBM works. Run `make setup`, `make contracts`, `make contracts-check`, `make test`, `make check`, and `make smoke`. `make demo`, full frontend, SSE, and LinuxONE verification remain P1 and must not be claimed. Open reviewed PRs to main; never direct-push, deploy, or change remote resources without authorization.
```
