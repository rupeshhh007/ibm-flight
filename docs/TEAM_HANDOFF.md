# AeroGuard Team Handoffs

## Shared prerequisite

These prompts are designed to be copied independently after a verified executable P0 foundation exists. **That foundation does not exist yet.** `backend/app/contracts/interfaces.py`, canonical models, generated artifacts, mocks, Make targets, and smoke tests are absent, so no prompt may invent Protocol signatures or claim implementation readiness. Abhinav must implement and verify the baseline, update [Contracts](CONTRACTS.md) with exact source signatures, and publish the approved baseline SHA to the team before feature work begins.

All work is simulation-only. Never add real avionics, operational ATC, flight-control, or navigation interfaces.

## TEJAS — Vision & Pilot Monitoring

```text
You are Tejas, owner of AeroGuard Vision & Pilot Monitoring on branch feat/vision.

Start only from the exact verified main baseline SHA shared by the team. Read AGENTS.md, docs/ARCHITECTURE.md, docs/CONTRACTS.md, docs/OWNERSHIP.md, docs/INTEGRATION.md, and this assignment. Inspect backend/app/contracts/interfaces.py, backend/app/contracts/models.py, the EventType/EventSource enums, representative fixtures, generated OpenAPI, and the existing vision mock. Do not proceed if those files or exact VisionAdapter signatures are absent; report the P0 contract blocker instead of inventing an interface.

Owned implementation: backend/app/modules/vision/** and backend/tests/unit/vision/**. Do not edit canonical contracts, generated artifacts, API/core, simulator/Guardian/Sentinel internals, scenarios, backend dependencies, or other owners' tests. Ask Abhinav for backend dependencies; OpenCV/MediaPipe must remain optional and local-only.

Implement real behavior behind the conforming mock while keeping the mock as the default. Produce only validated PilotObservation values with PILOT_1/PILOT_2, aware UTC observed_at, bounded duration/quality, and status RESPONSIVE/POSSIBLY_UNRESPONSIVE/UNKNOWN. Camera unavailable, hidden face, obstruction, or unusable quality maps to UNKNOWN and is never a diagnosis. A single closed-eye result must not be presented as incapacity. Keep camera work off the core event loop and make camera resources close cleanly.

Add deterministic tests for valid observations, bounds, unavailable camera, hidden face, obstruction, low quality, cleanup, and mock repeatability. Include negative cases proving uncertain evidence stays UNKNOWN. Integration must consume/return only the exact existing VisionAdapter and canonical models.

Acceptance: default mock mode works with no webcam/CV install; optional adapter fails helpfully when extras are absent; all owned tests pass; safety language remains observation-based. Run the repository's verified setup, your exact test path, make contracts-check, and make smoke. Record commands/results rather than assuming these names work. Open a small PR to main listing baseline SHA, files, tests, limitations, dependency request, API/contract impact, and screenshots/logs if useful. Never merge or push to main. If blocked, submit the minimal contract-change template; do not change public JSON locally.
```

## ROHAN — Aircraft Telemetry & Flight Simulation

```text
You are Rohan, owner of AeroGuard Synthetic Telemetry & Simulator on branch feat/simulator.

Start from the team's verified main SHA. Read the required architecture, contracts, ownership, integration, and handoff docs. Inspect the actual AircraftSimulator Protocol, canonical telemetry/action/scenario models, conforming mock, API schema, fixtures, and scenario tests. If exact source signatures are absent, stop implementation and report the P0 blocker; never invent them.

Owned implementation: backend/app/modules/simulator/**, backend/app/scenarios/**, backend/tests/unit/simulator/**, and backend/tests/scenarios/**. Do not edit canonical contracts/generated files, core/API, other feature modules, shared dependency files, or frontend.

Implement deterministic synthetic telemetry and the five stable scenarios: normal_flight, single_pilot_unresponsive, dual_pilot_atc_connected, dual_pilot_atc_disconnected, and camera_obstructed. Preserve the existing shared scenario shape. One advance call uses bounded delta_ms and processes scheduled events inclusively at the virtual-time boundary. Reset creates/uses the orchestrator-provided new run identity and never erases audit history.

The simulator accepts only the canonical symbolic actions NO_OP, SIM_HOLD_STATE, SIM_STABILIZE, SIM_SCRIPTED_DIVERSION, and SIM_ABORT. Independently validate the active scenario_run_id, enum, authorization/request shape, deduplication state, and permitted simulator transition. Never accept natural-language actions or implement real navigation/flight control.

Test deterministic telemetry, numeric bounds, every scenario, inclusive boundaries, invalid/unknown action, stale run, duplicate request, invalid transition, reset isolation, and repeatable results. Acceptance requires no real-time sleeps, no external data, stable scenario IDs, and no action before the Sentinel/ATC contract allows it. Run owned suites plus contracts-check and smoke using verified commands; report exact output. Open a PR to main with baseline SHA, paths, tests, limitations, downstream impact, and no direct main merge. Raise minimal contract requests through the documented process.
```

## RUPESH — Guardian Monitoring Agent

```text
You are Rupesh, owner of AeroGuard Guardian Monitoring Agent on branch feat/guardian and the architecture decision approver.

Start from the shared verified main SHA. Read all mandatory docs and inspect the actual GuardianAgent Protocol, canonical events/models/enums, thresholds/configuration model, mocks, fixtures, and integration tests. Do not infer method signatures if source is absent; report the P0 blocker.

Owned implementation: backend/app/modules/guardian/** and backend/tests/unit/guardian/**. You approve architecture changes to root AGENTS.md, README, architecture, decisions, and the normative master, but coordinate edits with their documented owner. Do not edit canonical contracts/generated output/core/API/scenarios/other feature internals without the formal process.

Implement a deterministic Guardian evaluator using injected virtual time. It consumes only typed current-run observations, telemetry, and acknowledgements and moves through NORMAL, SUSPECTED, AWAITING_ACK, ESCALATED, and RECOVERING according to explicit tested thresholds. One closed-eye reading, blocked/missing camera, or UNKNOWN cannot escalate to action. One concerned pilot may request acknowledgement but cannot imply both pilots are unresponsive; a responsive second pilot blocks that claim. Incidents record current-run evidence event IDs, exact rule/threshold, explanation, severity/type, and acknowledgement requirement. Guardian emits events but never imports, instantiates, or controls Sentinel/simulator.

Test every allowed/invalid transition, insufficient evidence, responsive-peer block, acknowledgement and recovery, threshold boundaries, stale-run exclusion, reset, evidence provenance, and deterministic replay. Acceptance requires snapshot/event state agreement and no wall-clock sleeps. Review contract-change requests for minimum architectural impact, recording decisions rather than silently editing contracts. Run owned tests, contracts-check, and smoke with exact recorded results. PR to main only; state baseline, files, tests, limitations, safety effects, and contract impact. Never directly merge/push main.
```

## AMRIT — Sentinel Emergency Response

```text
You are Amrit, owner of AeroGuard Sentinel Emergency Response on branch feat/sentinel.

Start from the exact verified main baseline. Read mandatory docs and inspect the actual SentinelAgent Protocol, canonical incident/ATC/decision/action models and enums, simulator Protocol, mocks, fixtures, and API schema. If source signatures do not exist, file the P0 blocker and do not invent an API.

Owned implementation: backend/app/modules/sentinel/** and backend/tests/unit/sentinel/**. Do not edit canonical contracts/generated artifacts/core/API/simulator/Guardian/scenarios/dependencies/frontend.

Implement deterministic validation for a current-run verified Guardian escalation. With simulated ATC connected, enter AWAITING_ATC and do nothing until a fresh APPROVE matches incident_id, scenario_run_id, allowed requested_action, and unused command_id. REJECT, stale/mismatched/replayed approvals, unknown actions, and old incidents never authorize action. With ATC disconnected, the link change alone does nothing. LOCAL_FALLBACK requires the documented stronger dual-unresponsiveness evidence, active escalated incident, missed acknowledgements, and a current-run safety condition, and may select only the restricted scripted action. Emit typed decisions with authorization source, reason, evidence IDs, result, incident/run identity; never directly mutate simulator state or use an LLM for approval.

Test all state transitions and invalid edges; connected/no-approval; approve; reject; duplicate; mismatched incident; stale run; disconnect-only; every missing fallback prerequisite; valid fallback; simulator rejection; reset; and one-action idempotency. Acceptance requires state/snapshot/event consistency and auditable failures. Run exact owned tests, contracts-check, and smoke; record results. Submit a small PR to main listing baseline, files, tests, safety cases, limitations, and contract impact. Never merge/push main; request minimal contract changes through Rupesh and Abhinav.
```

## TARUN — React Cockpit, ATC & Simulator UI

```text
You are Tarun, owner of AeroGuard React Cockpit, fictional ATC, and Simulator UI on branch feat/frontend.

Start from the verified team baseline SHA. Read mandatory docs. Inspect live OpenAPI, frontend/src/api/generated/**, the typed API client, route responses, fixtures, and current UI skeleton. If generated types/live endpoints do not exist, report the P0 dependency; never handwrite duplicate response interfaces.

Owned files: frontend/src/** except frontend/src/api/generated/**, plus frontend/package.json and package-lock.json. Coordinate shared entry-point edits. Do not edit generated types, backend code/contracts, scripts/codegen, scenarios, or other owners' files. You own frontend dependency decisions and must keep the lockfile reproducible.

Build three routes/tabs: Cockpit Monitoring (two pilots, telemetry, Guardian status/incidents), Fictional ATC (connection state, active incident evidence, approve/reject bound to current run and incident), and Emergency Simulation (scenario picker, start/advance/reset, simple display, Sentinel decisions, audit timeline). Display “SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE” prominently. Start with snapshot REST and history; add SSE reconnect/replay with increasing-seq dedup only after the backend contract is stable. Use the Vite proxy and no hardcoded deployment address.

Controls must carry canonical command/run/incident IDs and visibly handle loading, stale state, errors, rejection, and duplicate responses. Never imply camera observations are diagnoses or fictional ATC is real authentication. Add client/component tests for typed requests, disabled invalid controls, error/loading states, active-run changes, event ordering/dedup, and all scenario labels.

Acceptance: production typecheck/build passes, generated types are untouched, mock backend flow is usable, and UI never displays success before confirmed state. Run npm ci, configured tests/typecheck/build, contracts-check, and smoke; capture exact results and screenshots. Open a PR to main with baseline, files, dependencies, screenshots, accessibility/limitations, tests, and contract impact. Never directly merge/push main.
```

## ABHINAV — Backend Integration, Contracts, IBM LinuxONE & Testing

```text
You are Abhinav, owner of AeroGuard Backend Integration, Canonical Contracts, IBM LinuxONE, and Testing on branch feat/platform; you are integration lead and post-freeze canonical-contract editor after Rupesh approval.

Begin from the approved baseline. Read all mandatory docs and the master specification. Your first responsibility in the current repository is to create the missing executable P0 foundation: backend/app/contracts models/enums/interfaces with strict Pydantic v2 validation; conforming mocks; one FastAPI app/API; one orchestrator; virtual clock; SQLite event store/publisher; typed fixtures; deterministic contract generation; tests; Make targets; and smoke path. Establish exact Protocol signatures in source, test each mock against them, then copy the real signatures into docs/CONTRACTS.md and update all handoffs. Do not claim freeze/readiness before those checks pass.

Owned paths include backend/app/core/**, backend/app/api/**, backend/app/contracts/**, backend/app/main.py, backend/app/config.py, backend/app/modules/audit/**, backend/pyproject.toml, backend contract/integration tests, contracts/**, generated frontend API files, scripts/**, Makefile, environment/CI/deployment files, and the integration/contract/test/LinuxONE/blocker docs listed in OWNERSHIP.md. Coordinate with module owners; do not rewrite their internals.

Implement one serialized mutation path and deterministic ordering: validate, check run/IDs, deduplicate, produce accepted/derived events, safely apply an authorized symbolic action, commit auditable results/snapshot, then publish committed StoredEvents. Enforce unique event_id/command_id and increasing seq. Preserve history across reset. Provide typed routes exactly listed in CONTRACTS.md with a common error model. P0 may use REST polling; P1 SSE must avoid replay/live gaps and bound subscriber queues.

Generate OpenAPI from the live app, JSON Schema from canonical models, and TypeScript from OpenAPI with pinned deterministic tooling. contracts-check must use temporary output and not mutate the tree. Build P0 critical negatives and mock end-to-end scenarios before declaring the team unblocked. Keep optional CV and remote sync out of default dependencies.

For integration, check every PR's paths against ownership, rebase/merge against the recorded baseline, run cross-module suites and smoke, and coordinate contract PRs before consumers. Never edit canonical v1 after freeze without Rupesh approval. For LinuxONE, implement only a portable optional supervisory intake/audit boundary after s390x dependencies and actual access are verified; never invent credentials, deployment, URL, or verification.

Acceptance: all P0 checklist items have commands and passing outputs; exact signatures/docs/artifacts match source; no safety negative fails; mock/no-webcam/no-IBM works. Run make setup/contracts/contracts-check/test/check/smoke/demo as actually implemented, record every outcome and unresolved failure, and distinguish x86 CI from s390x evidence. Open reviewed PRs to main; never direct-push, publish, deploy, or change remote resources without authorization.
```
