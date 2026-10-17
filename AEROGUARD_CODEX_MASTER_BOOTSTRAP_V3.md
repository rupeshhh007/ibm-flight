# AEROGUARD — CODEX MASTER BOOTSTRAP PROMPT (V3)

> **Paste this entire file into the FIRST Codex session, or place it at the repository root and tell Codex: “Read AEROGUARD_CODEX_MASTER_BOOTSTRAP_V3.md completely, then execute it. Do not stop after planning.”**
>
> This is a *foundation-building* task. The six developers start feature work **only after** the foundation is committed and its contracts are verified.

## 0. Your role and goal

Act as **Principal Architect, Contract Engineer, and Bootstrap Implementer** for **AeroGuard**, a six-person IBM Z Datathon aviation-emergency **simulation** project. Every teammate will use an AI coding agent on an independent Git feature branch, so your primary mission is to eliminate conflicting schemas, invented endpoints, incompatible state machines, overwritten files, and last-minute integration failures.

**DO THE WORK:** inspect the local repository; create actual source files and dependencies; implement typed contracts; generate OpenAPI/TypeScript types; implement a working mock vertical slice; add deterministic tests and CI; run checks and repair failures; create personalized handoff prompts based on actual code. Do not deliver only an architecture plan or disconnected placeholders.

**Time constraint:** the hackathon is only 24 hours. Aim to make the initial usable foundation available to the other five agents as rapidly as possible. Work in two passes:

- **P0 / launch gate (target ~60–90 minutes, not a promise):** canonical contracts, module interfaces, file ownership, local API + mock scenario + basic event store, contract generation, tests, handoffs. At this point the team can branch and start.
- **P1 / polish after launch:** SSE replay, full frontend skeleton, expanded scenarios, CI hardening, optional remote sync boundary. Never delay all teammates merely to perfect optional scaffolding.

Do not claim that a checkpoint passed unless you actually ran its checks. Work without paid API keys or external credentials. Avoid asking routine design questions: choose simple consistent defaults and document them. If a needed decision is genuinely blocking, state it precisely.

**CRITICAL: DO NOT** delete existing files, reset/force-push Git history, publish a GitHub repo, use live aircraft APIs, deploy anything, or change remote resources without explicit authorization. If this is an existing repo, first inspect and preserve it.

## 1. Project definition and safety boundary

**AeroGuard** is a real-time cockpit monitoring and simulated emergency-response system. Its two separate logical agents are:

- **Guardian:** receives camera-derived pilot observations, synthetic aircraft telemetry, alert acknowledgements, and simulated ATC connectivity; evaluates multiple pieces of evidence; tracks suspicion, warnings and incidents; emits typed events; **never directly controls the flight simulator**.
- **Sentinel:** consumes validated Guardian escalations and simulated ATC decisions; checks current scenario, incident, authorization and permitted state transitions; may request only **explicitly allowed symbolic simulation actions** from the simulator. Local disconnected mode demonstrates a *restricted scripted fallback*, not a real autopilot.

The project includes local deterministic scenarios, a fictional ATC console, a web dashboard, auditable event history, and an optional IBM LinuxONE supervisory service. All telemetry is synthetic. Camera observations are uncertain and are **not diagnoses of unconsciousness**. No real aircraft, avionics, ATC networks, flight guidance, automated navigation, aircraft-control interfaces or real landing algorithms. Mark the UI/docs **SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE**.

AI/ML is appropriate for **Tejas's vision observation adapter** and a later optional anomaly detector. Deterministic state machines guard escalation and action authorization. Do not introduce an LLM into the simulation-action approval path. LLM summaries are optional and must not be needed to operate locally.

## 2. Exactly six named owners (DO NOT REMAP)

| Member | Person | Responsibility | Branch | Primary owned directory |
|---|---|---|---|---|
| 1 | **Tejas** | Computer Vision & Pilot Monitoring | `feat/vision` | `backend/app/modules/vision/` |
| 2 | **Rohan** | Aircraft Telemetry & Flight Simulation | `feat/simulator` | `backend/app/modules/simulator/`, `backend/app/scenarios/` |
| 3 | **Rupesh** | Guardian Monitoring Agent | `feat/guardian` | `backend/app/modules/guardian/` |
| 4 | **Amrit** | Sentinel Emergency Response Agent | `feat/sentinel` | `backend/app/modules/sentinel/` |
| 5 | **Tarun** | Frontend, Cockpit & ATC UI | `feat/frontend` | `frontend/src/` excluding generated contract files |
| 6 | **Abhinav** | Backend Integration, IBM LinuxONE & Testing | `feat/platform` | `backend/app/core/`, `backend/app/api/`, deployment/CI/contracts |

**Governance:** Rupesh is architectural decision approver; Abhinav is integration lead and sole post-freeze editor of canonical contracts (after approval). This does not authorize either to silently rewrite another person's feature implementation. Everyone owns and tests their module. Abhinav coordinates integration and cross-module regression tests.

Create `docs/OWNERSHIP.md` with a **precise ownership table, including shared files, generated files, dependency files, scenarios and tests**. Ensure there is a **single named owner** for each writable shared path. For shared dependency updates (e.g. `backend/pyproject.toml`, `frontend/package.json`) the feature owner files a request; Abhinav coordinates backend/infra, Tarun owns frontend dependency files, with a PR review. Do not allow independent agents to edit generated files.

## 3. Stack, scope, and architectural boundaries

- Python **3.11** backend; FastAPI + Pydantic v2; single process and a single event-orchestrator composition root; sqlite3 or a lightweight SQLite abstraction. Python environment under `backend/.venv`, ignored by Git.
- React + Vite + TypeScript frontend; npm lockfile checked in; Vite development proxy to local backend; `npm ci` for reproducible installs.
- SSE from backend to browser (events + reconnect/replay), REST for commands and snapshots.
- OpenAPI generated from the **live FastAPI app**, TypeScript API types generated from OpenAPI, JSON Schema generated from canonical Pydantic models. No independent handwritten duplicates.
- `pytest` + FastAPI HTTP client, TypeScript typecheck/build, GitHub Actions.
- Vision CV stack (OpenCV/MediaPipe) **optional and local-only**, installed by Tejas; backend and LinuxONE supervisory path must boot without it.
- LinuxONE uses Linux **s390x**. Do not assume Apple Silicon or x86 wheels/images work there. Keep LinuxONE for supervisory event intake, API/audit/analytics only. Actual deployment is contingent on verified access and architecture-compatible dependencies.
- **No** Redis, Kafka, Celery, Kubernetes, multiple backends, LangGraph, CrewAI, paid APIs, or OAuth as initial dependencies. Do not turn the simulated ATC authorization control into a claim of production authentication.

Keep the event flow **one-way and explicit**:

`Mock/Real Vision + Synthetic Simulator + Pilot Acks -> Orchestrator -> Guardian -> Guardian incident -> Sentinel (ATC/fallback gate) -> Authorized symbolic simulator action -> Stored audit events -> REST/SSE frontend`

Only the orchestrator owns module wiring, event dispatch, and persistence ordering. Feature modules must not privately import or instantiate other feature modules. All dependencies use declared interfaces. All scenario-time logic uses an injectable virtual clock; **no test should sleep for minutes**.

## 4. Minimum meaningful file tree

Create these, adjusting package layout only if necessary and documenting the actual result:

```text
AGENTS.md
README.md
Makefile
.gitignore
.env.example
docs/
  ARCHITECTURE.md
  CONTRACTS.md
  OWNERSHIP.md
  CONTRACT_CHANGE_PROTOCOL.md
  INTEGRATION.md
  TEAM_HANDOFF.md
  DEMO_RUNBOOK.md
  TEST_MATRIX.md
  IBM_LINUXONE.md
  DECISIONS.md
  BLOCKERS.md
contracts/
  generated/openapi.json
  generated/events/*.schema.json
  fixtures/*.json
backend/
  pyproject.toml
  app/
    main.py
    config.py
    contracts/{enums.py,models.py,interfaces.py}
    api/{routes.py,dependencies.py}
    core/{orchestrator.py,event_store.py,event_bus.py,clock.py}
    modules/{vision,simulator,guardian,sentinel,audit}/
    scenarios/{catalog.py,runner.py}
  tests/{unit,contracts,integration,scenarios}/
frontend/
  package.json
  package-lock.json
  src/
    App.tsx
    api/{client.ts,events.ts,generated/}
    pages/{CockpitPage.tsx,ATCPage.tsx,SimulationPage.tsx}
    components/
    hooks/
scripts/{export_contracts.py,verify_contracts.py,smoke_test.py,dev.sh}
.github/{workflows/ci.yml,pull_request_template.md}
```

Do not fill the tree with empty files. Build a **minimal working slice** first; create subsequent paths only when needed. Properly initialize Python packages. Include working `.env.example` without secrets. Preserve existing repo content.

## 5. Mandatory top-level AGENTS.md

Keep `AGENTS.md` concise and imperative. It must instruct every agent to read `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`, `docs/OWNERSHIP.md`, `docs/INTEGRATION.md`, and its assignment in `docs/TEAM_HANDOFF.md` before writing code. Require:

1. Only modify owned files and owned tests; leave other owners' files untouched unless approved.
2. Canonical Pydantic models, public interfaces, endpoint schemas, generated JSON Schema/OpenAPI/TypeScript files are **frozen contract v1** after bootstrap.
3. Never manually edit generated artifacts; use the generator.
4. Never create a second API server, alternate event schema, alternate state-machine enum, parallel DB, or direct feature-to-feature internal imports.
5. All simulator actions require Sentinel authorization and independent simulator validation; no LLM-generated flight action.
6. Add negative tests, regression tests, and maintainable type hints. Preserve stable scenario IDs.
7. Before PR: run applicable tests plus contract drift checks; report exact commands/results/blockers.
8. Never push to `main`, force-push shared refs, commit secrets, claim unexecuted tests passed, or perform destructive Git operations.
9. If blocked by a contract, **write a small change request** instead of changing local JSON shapes.
10. Keep mock/no-webcam/no-IBM mode fully functional.

## 6. Canonical domain types — one authoritative source

Implement in `backend/app/contracts/` using Pydantic v2 and strict enums/validation. Choose documented Python and JSON casing (`snake_case` on the wire), UTC time handling, numeric ranges, and error shape; avoid leaky untyped dictionaries.

### 6.1 Event representation

Define `DomainEvent` (before storage) and `StoredEvent` (with `seq: int` assigned by SQLite). Event fields:

- `event_id: UUID`
- `schema_version: Literal["1.0"]`
- `event_type: EventType` (enum)
- `occurred_at: aware UTC datetime`
- `source: EventSource` (enum)
- `scenario_run_id: UUID`
- `correlation_id: UUID`
- `causation_event_id: UUID | None`
- `payload: discriminated, typed event-payload union`
- for `StoredEvent` only: `seq: positive int`

**Important:** enforce `event_type <-> payload` consistency. You may use one discriminated union of event subtypes if easier/safer in Pydantic; document the exact public JSON representation. Do not permit unrelated payloads to be attached to an event type.

Stable required events:
`SCENARIO_STARTED`, `SCENARIO_ADVANCED`, `PILOT_OBSERVATION`, `TELEMETRY_UPDATED`, `PILOT_ACKNOWLEDGED`, `ATC_LINK_CHANGED`, `GUARDIAN_INCIDENT`, `ATC_DECISION`, `SENTINEL_DECISION`, `SIMULATOR_ACTION`, `SCENARIO_RESET`, `SCENARIO_COMPLETED`. Add only essential additional events **during bootstrap**, document and freeze them.

Database sequence IDs are globally increasing within a local store; `scenario_run_id` identifies a run. Source-generated timestamps and commit order are distinct. Events from a reset/old run **must never drive the current run's state**. Append-only event history must remain inspectable across resets.

### 6.2 Typed payloads and commands

Create real models and enums for:

- **PilotObservation:** `pilot_id` (`PILOT_1|PILOT_2`), `observed_at`, `observation_status` (`RESPONSIVE|POSSIBLY_UNRESPONSIVE|UNKNOWN`), `camera_available`, `face_visible`, `eyes_closed`, `observation_duration_ms`, `observation_quality` (bounded 0..1). `UNKNOWN`/camera obstruction is never proof of incapacitation.
- **AircraftTelemetry:** `aircraft_id`, `simulation_time`, `altitude_ft`, `airspeed_kts`, `heading_deg`, `latitude`, `longitude`, `flight_phase`, `active_warning_codes`. Explicitly synthetic; document bounds.
- **PilotAcknowledgement:** `command_id: UUID`, `scenario_run_id`, `pilot_id`, `alert_id`, `acknowledged_at`.
- **GuardianIncident:** `incident_id`, `incident_type`, `severity`, `guardian_state`, `evidence_event_ids`, `explanation`, `acknowledgement_required`, `created_at`.
- **ATCDecision:** `command_id: UUID`, `scenario_run_id`, `incident_id`, `decision: APPROVE|REJECT`, `requested_action`, `operator_id`, `issued_at`.
- **SentinelDecision:** `decision_id`, `incident_id`, `scenario_run_id`, `sentinel_state`, `action_type`, `authorization_source`, `reason`, `evidence_event_ids`, `executed_at`, `result`.
- **CommunicationStatus:** `atc_link_connected`, `last_change_at`, `remote_sync_connected`, `pending_sync_count` (mock remote sync okay).
- **SystemSnapshot:** active `scenario_id`, `scenario_run_id`, virtual-time value, both pilot states, current telemetry, Guardian state, Sentinel state, active incident, simulated ATC link, last permitted simulator action, `latest_event_seq`, and clear demo status text.
- **CommonApiError**, scenario start/advance/reset requests and responses, ATC/link/ack commands and responses, list and pagination responses.

These model names/field names are the initial canonical public contract. If you must resolve ambiguity (e.g. virtual-time type), do it **once at bootstrap** and write down the exact choice. Strictly validate UUIDs, enum values, timestamps, and command/run IDs. Create validated representative fixtures under `contracts/fixtures/`.

### 6.3 Enums and state invariants

Guardian states: `NORMAL`, `SUSPECTED`, `AWAITING_ACK`, `ESCALATED`, `RECOVERING`.

Sentinel states: `STANDBY`, `AWAITING_ATC`, `LOCAL_FALLBACK`, `SIM_ACTION_RUNNING`, `COMPLETED`, `ABORTED`.

Allowed symbolic simulator actions: `NO_OP`, `SIM_HOLD_STATE`, `SIM_STABILIZE`, `SIM_SCRIPTED_DIVERSION`, `SIM_ABORT`. These must not map to real avionics or navigation commands.

Declare transitions and prerequisites in a machine-readable/testable or clearly documented transition table. All invalid transitions fail in a predictable manner and produce an audit result; they must not silently execute. State snapshots and emitted decisions must agree.

### 6.4 Public module Protocols (freeze before parallel development)

Implement typed `Protocol` or ABC interfaces for:

- `VisionAdapter`: produces validated observation(s), mock/optional real adapter.
- `AircraftSimulator`: start/reset/advance deterministic scenario, apply permitted symbolic action, return typed telemetry/state.
- `GuardianAgent`: consume typed events, expose typed state/incident, emit typed domain events.
- `SentinelAgent`: consume validated incident/ATC/link events, expose typed state, emit typed decision/action requests.
- `EventStore`: append atomic/ordered events, read after sequence, fetch latest snapshot/history.
- `EventPublisher`: publish committed stored events to live subscribers.
- `Clock`: virtual-time now()/advance() without sleeping.
- `RemoteSyncAdapter`: **optional mock only** for bootstrap.

The prompt deliberately does not prescribe raw signatures: **Codex must establish exact signatures in `interfaces.py`, implement interface-conforming mocks, test those mocks, copy the real signatures into `docs/CONTRACTS.md`, and generate each developer handoff against those signatures**. Nobody should invent signatures later.

## 7. Guardian baseline state-machine contract

Guardian receives typed observations, telemetry, acknowledgements and current virtual time. Use typed configurable thresholds and a deterministic evaluator.

- One closed-eye observation, a missing face, or a blocked camera alone **cannot** trigger autonomous simulation action.
- Mark unusable camera evidence `UNKNOWN`; do not silently upgrade it to `POSSIBLY_UNRESPONSIVE`.
- One possibly unresponsive pilot may cause suspicion/acknowledgement request, **not** unsupported dual-pilot incapacity or takeover.
- Synthetic repeated observations, unanswered alerts, and supporting conditions may escalate only through documented transitions.
- Evidence event IDs and the exact rule/threshold used are stored in an incident.
- A responsive second pilot blocks claims that both pilots are unresponsive.
- Recovery/acknowledgements and scenario reset have explicit behavior.

**Use an injected virtual clock and scripted observations.** No wall-clock sleeps in test cases. The real webcam adapter must not be required for the default mock demo.

## 8. Sentinel and simulator authorization contract

Sentinel may act only on a **current-run verified Guardian escalation**. The connected/disconnected pathways are explicit:

- **ATC connected:** emit `AWAITING_ATC`, reject stale/mismatched/replayed approval, and wait for an affirmative simulated ATC decision referencing the active `incident_id`, `scenario_run_id`, and an allowed action. `REJECT` is not approval. The frontend's ATC console is fictional, not a real authorization system.
- **ATC disconnected:** changing the link to disconnected **by itself must not cause an action**. The local fallback is allowed only with documented stronger synthetic evidence of dual unresponsiveness, active escalated incident, missed acknowledgements, and a current-run safety condition. It may select only the approved symbolic fallback action.
- All decisions carry `authorization_source`, `reason`, evidence IDs, incident/run IDs, and result.
- Repeated commands/actions cannot execute twice. An action for a previous scenario run is rejected.
- Rohan's simulator **independently** validates action enum, active run, and permitted transition; it does not execute natural-language commands.
- No real aircraft guidance/control code.

Baseline implementations may initially be mocks, but the contract and negative tests must be real.

## 9. Orchestration, concurrency, persistence, and events

Use **one serial domain-command processing path** suitable for a single FastAPI worker. Clearly choose sync/async boundaries; if stateful, protect mutations using an application-level lock or explicit serialized command processor. Avoid multiple Uvicorn worker processes with independent in-memory state. Cameras must not block the core event loop.

Command transaction/processing intent:

1. Validate input against canonical typed model.
2. Validate `scenario_run_id`, command ID, current state and any incident ID.
3. Deduplicate a command before applying side effects.
4. Append accepted input event(s) and derived decision events in deterministic order.
5. Apply permitted state change/action through explicit interface.
6. Persist auditable outcome, update current snapshot and publish only **committed** stored events.

Design the transaction boundary so retries do not repeat simulator actions. If full atomic reconstruction is too much for bootstrap, implement the simplest consistent approach and document restart guarantees/limits precisely. Do not claim production exactly-once delivery.

SQLite tables/indexes must prevent duplicate `event_id` and duplicate `command_id`, store global increasing `seq`, enable `events after seq` query, and retain logs across a reset. A new start/reset must create a new `scenario_run_id`. Avoid silent loss of event history when resetting.

**SSE:** persisted `seq` is SSE `id`. A new subscriber can replay events after `after_seq` / `Last-Event-ID`, then switch to live events with **no race-induced gap**; define how server avoids a replay/live subscription gap. Browser drops duplicate or out-of-order seq. Bound subscriptions/queues; handle browser disconnect; retain REST history fallback. If complex live streaming delays P0, ensure event-history REST and frontend polling work first, then add SSE during P1.

**Remote sync:** optional interface and mock, never required for local control. `atc_link_connected` is an injected **simulation value**, not a real TCP outage. Distinguish it from browser/server connectivity and LinuxONE sync status.

## 10. REST API (freeze route names and payloads)

Implement working typed FastAPI endpoints (mock values acceptable if clearly identified):

```
GET  /healthz
GET  /readyz
GET  /api/v1/state
GET  /api/v1/scenarios
POST /api/v1/scenarios/start
POST /api/v1/scenarios/advance
POST /api/v1/scenarios/reset
POST /api/v1/pilots/acknowledge
POST /api/v1/atc/decision
POST /api/v1/communications/link
GET  /api/v1/incidents
GET  /api/v1/events?after_seq=0&limit=100
GET  /api/v1/events/stream?after_seq=0
```

All responses and commands are Pydantic models exposed in OpenAPI, with a consistent error shape; define validation for `limit`, run identity, permissions, stale IDs, and invalid actions. Mutating endpoints require a `command_id` and current `scenario_run_id` where applicable; `scenario/start` uses command ID and returns newly created run ID; for reset, document which run is being reset. Return same result or documented duplicate response for replays; don't execute twice.

Local dev Vite proxy `/api` (and `/healthz`, `/readyz` as needed) to `127.0.0.1:8000`; avoid hardcoded deployment addresses. API is local/demo-only by default and must not be casually exposed to the public internet.

## 11. Deterministic scenario catalogue and tests

Freeze IDs:

1. `normal_flight`: pilot observations responsive; no Guardian escalation/no Sentinel action.
2. `single_pilot_unresponsive`: one pilot appears unresponsive; other remains responsive and acknowledges as appropriate; no autonomous action.
3. `dual_pilot_atc_connected`: combined synthetic evidence triggers escalation; Sentinel **waits for explicit valid simulated ATC APPROVE**; before approval no action; approval authorizes one symbolic action; REJECT/duplicate approval cannot run it.
4. `dual_pilot_atc_disconnected`: combined stronger synthetic evidence and missed acknowledgements; no simulated ATC; Sentinel performs only permitted symbolic local fallback and audits it.
5. `camera_obstructed`: unavailable/uncertain camera observation; no action from obstruction alone.

Rohan owns scenario catalogue/runner **after** bootstrap. During bootstrap, implement their shared shape and baseline fixture tests. One `POST /scenarios/advance` call advances virtual time by bounded `delta_ms`, runs scheduled synthetic observations, and exposes the new state; document whether events at the boundary are inclusive (recommend inclusive). Tests never wait real seconds. `reset` isolates old runs and does not erase audit history.

At least these negative tests must exist before parallel development:
- bad event payload/type mismatch rejected;
- blocked camera not proof of incapacitation;
- single responsive pilot prevents dual-incapacity action;
- connected ATC path cannot act without approval;
- disconnected toggle alone cannot trigger fallback;
- `REJECT`, duplicate, mismatched and stale approval cannot cause action;
- unauthorized enum/action rejected by simulator;
- reset invalidates old run commands;
- event sequences increase and replay does not skip committed events.

Mock e2e integration tests must remain executable even before real implementations arrive.

## 12. Frontend contract and independent Tarun workflow

Initialize React/Vite/TypeScript with three simple routes or tabbed screens:

- Cockpit Monitoring: two observation panels, telemetry, Guardian status, incidents.
- Fictional ATC: connected state, incident evidence, approve/reject controls bound to active run/incident.
- Emergency Simulation: scenario picker, start/advance/reset, map/path placeholder or simple 2D flight display, Sentinel decisions, audit timeline.

Use typed API client and **generated** frontend API types, never independently defined response interfaces. Start with snapshot REST + event history; add SSE subscription/reconnect dedup in P1. Show loading/errors and status banner. Avoid expensive visual design during bootstrap: Tarun will finish it.

Owned frontend paths: Tarun may edit frontend `src` except generated types, and frontend `package.json`/lockfile. Abhinav owns only the generated API files and codegen scripts. Coordinate modifications to a shared entry point through code review.

## 13. Contracts generation and drift gates

Implement:

- `make contracts`: regenerate `contracts/generated/openapi.json`, JSON Schemas for domain events, and `frontend/src/api/generated/*` from the canonical FastAPI/Pydantic code.
- `make contracts-check`: regenerate to temporary storage and **compare artifacts bytewise/diff**, exit nonzero on drift, **do not mutate the working tree**.
- Fixture validation tests load every `contracts/fixtures/*.json` using correct canonical models.
- `docs/CONTRACTS.md` records exact actual module Protocol signatures, enum values, URL request/response types, and example valid payloads; not imagined API shapes.

Choose deterministic output formatting and stable file order; avoid timestamps or absolute paths in generated artifacts. Pin the code-generator version. CI must detect drift.

## 14. Makefile, local development, and CI

Implement and test sensible targets:

```
make setup
make backend
make frontend
make dev
make contracts
make contracts-check
make test
make check
make smoke
make demo
```

- `make setup`: validate Python 3.11, Node/npm; create `backend/.venv`; install backend editable deps/test extras; `npm ci` in frontend; error helpfully if prerequisites absent. Avoid implicitly installing optional CV deps.
- `make dev`: start API and Vite dev server, print URLs, terminate both cleanly with Ctrl+C.
- `make test`: backend unit/contract/scenario tests.
- `make check`: pytest, contract drift, Python lint/typecheck if configured, `tsc`/frontend production build.
- `make smoke`: start backend or use FastAPI test transport; run a real API-based happy/negative path and print results.
- `make demo`: stable local demo instructions or start command, no cloud credentials.

Create `.github/workflows/ci.yml` for Linux x86 GitHub Actions using the same commands (don’t claim this verifies s390x). Include `.github/pull_request_template.md` requiring: owned files, API compatibility, tests with commands, screenshots if UI, blockers, downstream impact.

## 15. IBM LinuxONE realistic integration

Write `docs/IBM_LINUXONE.md`: identify the portable supervisory/event-receiver/backend portion; avoid CV packages on s390x; verify wheel and container architecture before deployment; include environment requirements and tests for actual endpoint/event ingestion; separate unverified conceptual integration from actual deployed functionality. Never invent IBM credentials, running services, ports, or deployed URL. If credentials absent, keep local mock remote-sync and make the demo work. Do not block teammates on deployment.

Abhinav owns deployment/test integration. Remote supervisory services may collect incidents and audit events but must not sit in the local simulator's approval/control critical path.

## 16. Shared-file policy and contract-change procedure

Create `docs/CONTRACT_CHANGE_PROTOCOL.md` with a simple, enforceable workflow:

1. Developer writes a change request in PR description or `docs/BLOCKERS.md`: exact existing contract, proposed field/signature/change, why unavoidable, owner impact.
2. Rupesh approves/rejects architecture-breaking changes; Abhinav assesses consumers.
3. Abhinav edits canonical source models/Protocol and regenerates artifacts; adds contract/fixture regression tests.
4. Merge the **contract PR first** (or explicitly coordinate an atomic cross-module PR with owner approvals).
5. Each affected module owner updates their code against the new contract; contract compatibility is tested before merge.
6. Do not silently add fields to local JSON, change enum literals, routes, database formats, or generated types.

For urgent hackathon blockers, prefer adapter shims inside the requesting module **without changing v1** if safe and well tested. If impossible, document the exact blocker and request minimal change. No generic catch-all JSON schemas that merely hide incompatibilities.

Ensure direct written ownership of: root `AGENTS.md`/architecture docs (Rupesh approval), canonical schemas/generators/CI/backend dependencies/core/API (Abhinav), scenarios (Rohan), frontend deps and source (Tarun), other feature modules (their named owners).

## 17. Six personalized Codex handoffs (REQUIRED P0 DELIVERABLE)

Create `docs/TEAM_HANDOFF.md` containing **six independent complete prompts**, individually named:

- **TEJAS — Vision & Pilot Monitoring**
- **ROHAN — Synthetic Telemetry & Simulator**
- **RUPESH — Guardian Monitoring Agent**
- **AMRIT — Sentinel Emergency Response**
- **TARUN — React Cockpit/ATC/Simulator UI**
- **ABHINAV — Backend Integration/Contracts/IBM LinuxONE/Testing**

Each prompt must tell its person to:

- Create/check out the correct feature branch from the same **verified main baseline**.
- Read AGENTS.md, ownership, contracts, interfaces, API schema and integration docs.
- Inspect the **actual existing public Protocol signatures, types and mocks**, with concrete file paths and exact model names (copy them from the code you wrote).
- Change **only** their assigned implementation files/owned tests/dependencies as allowed; do not alter public contracts/generated types or other owners' internals.
- Implement real behavior behind already working baseline mocks, keeping mocks usable for tests.
- Use deterministic unit tests and integration against stable mocked peers.
- Run exact setup/tests appropriate to their module, plus `make contracts-check` and `make smoke` if possible.
- If blocked, report a **minimal contract change request**, not unilateral redesign.
- Create a PR targeting main, never directly merge/push to main; include exact test outputs, files changed, limitations and API impacts.

These prompts must reference **real code that exists**, not imagined future method names. Assign Abhinav explicit merge/rebase smoke-check responsibilities; assign Rupesh architecture-review responsibilities. Document a stand-up/checkpoint protocol (`docs/INTEGRATION.md`) so the team detects blockers early.

## 18. Integration cadence and merge acceptance

Create `docs/INTEGRATION.md` with the following practical flow:

- Initial architect finishes P0, runs required gates, makes a **local foundation commit** when instructed/appropriate, and shares main baseline. **Do not publish a remote without authorization.**
- All teammates clone **the same main SHA** and each makes a feature branch. Record baseline SHA in team chat.
- Commit only owned files; open small PRs as soon as meaningful tests pass. Abhinav checks changed paths for ownership violations.
- Integration priority: Rohan's simulator + Rupesh's Guardian -> Amrit's Sentinel -> Tarun's real frontend -> Tejas's camera adapter -> IBM remote integration. **Coding can run concurrently.**
- CI `make check`/`make smoke` must remain green; no last-minute direct-to-main changes.
- For contract blocker, post proposed change immediately; do not hold a huge unmergeable PR.
- Set quick team sync/checkpoints after foundation, at ~4 hours, ~8 hours, ~12 hours, ~17 hours, ~21 hours relative to hackathon start. Do not invent exact clock times.
- Keep a stable known-good tagged demo commit as soon as the first full scenario works. In the final ~3 hours prioritize fixes/testing/presentation over new features.
- Maintain `docs/BLOCKERS.md` with owner, issue, reproduction, impact, proposed fix, status; never claim a blocker is resolved without retesting.

If GitHub required checks/branch protection are not configurable, write a manual merge checklist. Avoid making merge order rigid when independently functioning changes are ready.

## 19. Acceptance gates: prove that all six can start

**P0 LAUNCH GATE** — team may start feature work only after:

- [ ] `AGENTS.md` and exact ownership table written, with six names correctly mapped.
- [ ] Canonical Pydantic models/typed module Protocols import and validate.
- [ ] Frozen v1 event enum / state enums / simulator actions documented.
- [ ] OpenAPI + TypeScript code generation and drift-check scripts run.
- [ ] Backend starts; `GET /healthz` and `GET /api/v1/state` respond.
- [ ] One deterministic scenario can start, advance, and produce stored ordered events.
- [ ] A minimal Guardian->Sentinel->Simulator **mock** vertical slice executes with required authorization gates.
- [ ] Critical negative tests (camera unknown, no ATC approval, invalid action, old-run command) pass.
- [ ] `docs/TEAM_HANDOFF.md` contains six **usable actual-interface-based** prompts.
- [ ] Exact setup and tests are documented with verified commands.

If optional frontend or SSE work is incomplete, report it as P1 explicitly; do not falsely mark P0 finished. Teammates can still start against working REST/mock contracts.

**P1 BASELINE GATE** — finish as soon as possible:

- [ ] Five scenario IDs deterministic and testable.
- [ ] Replay-safe SSE + REST event history.
- [ ] Working simple React navigation and typed client.
- [ ] `make setup`, `make dev`, `make check`, `make smoke`, `make demo` verified.
- [ ] CI config present, no unused secrets.
- [ ] Complete README, demo runbook and IBM documentation with honest statuses.

Never represent mock implementations as completed feature work. No invented performance, ML accuracy or deployment metrics.

## 20. Execution order and final response

1. Inspect repository/Git and local environment; preserve existing work.
2. Create minimal project structure, root AGENTS.md, ownership/governance docs and pinned dependency setup.
3. Implement canonical typed contracts, module interfaces, fixtures, codegen, and tests. **Freeze v1.**
4. Implement local deterministic mock vertical slice and actual API endpoints (including persistence and basic error handling), validate safety invariants.
5. **Immediately generate personalized six prompts and report P0 readiness accurately** so other agents can start. Don't keep everyone waiting on visual polish.
6. Implement P1 (SSE, frontend skeleton, CI, expanded test coverage, LinuxONE integration boundary docs), retest.
7. Deliver concrete output: files created; exact contracts/API signatures; verified commands; actual tests/failures; P0/P1 status; exact handoff file; real blockers; Git state; note remote publish has NOT happened unless explicitly authorized.

Run checks and fix failures rather than stopping after file creation. Do not claim you built real AI pilot incapacitation detection or real aircraft emergency control.

**BEGIN NOW. The result must let Tejas, Rohan, Rupesh, Amrit, Tarun and Abhinav build independently against the same executable versioned contracts without inventing new APIs.**
