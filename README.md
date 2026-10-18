# AeroGuard

> **SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE**

AeroGuard is an IBM Z Datathon project for demonstrating a safe, auditable aviation-emergency simulation. It combines uncertain camera-derived pilot observations, synthetic aircraft telemetry, deterministic incident evaluation, fictional ATC decisions, restricted symbolic simulator actions, and an operator dashboard. It does not connect to aircraft, avionics, operational ATC, or navigation systems.

## Project status (18 October 2026)

**Integrated local demo: merged into `main`.** Guardian (Rupesh), Sentinel (Amrit), deterministic simulator (Rohan), uncertainty-aware Vision adapter (Tejas), React/Vite frontend (Tarun), and the platform orchestrator/integration tests (Abhinav) are present. The UI has Flight Deck, Guardian, Sentinel, Vision, Black Box and Scenarios views. The default application remains the deterministic mock demonstration; real Guardian/Sentinel agents can be enabled explicitly with `AEROGUARD_AGENT_MODE=deterministic`. The optional vision camera adapter requires its own opt-in dependencies.

Frontend [PR #5](https://github.com/rupeshhh007/ibm-flight/pull/5) and platform [PR #8](https://github.com/rupeshhh007/ibm-flight/pull/8) merged on October 18, 2026. Before the final merge, the integrated combination passed 690 backend tests (10 optional skipped), 69 frontend tests, 100 backend integration tests (included within the backend total), contract drift verification, typecheck, frontend build, and the 18-event smoke path with exactly one authorized `SIM_STABILIZE`. The final `main` commit still needs a recorded local verification run.

**Not claimed:** operational aviation capability, real ATC identity, replay-safe SSE, deployed LinuxONE event intake, or `s390x` validation.

## Problem and proposed solution

Emergency-response demonstrations often blur uncertain observations, authorization, and action. AeroGuard makes those boundaries explicit:

1. A vision adapter emits observations, not medical diagnoses.
2. A synthetic simulator emits telemetry and accepts only enumerated symbolic actions.
3. Guardian combines evidence and manages suspicion, acknowledgement, escalation, and recovery; it never controls the simulator.
4. Sentinel validates a current-run Guardian escalation and either waits for an explicit simulated ATC approval or applies a tightly constrained scripted fallback.
5. The orchestrator serializes commands, stores ordered events, updates a snapshot, and publishes committed events.
6. A web UI presents cockpit, fictional ATC, scenario, and audit views.

The objective is a deterministic, locally runnable demonstration whose decisions can be explained and replayed without paid services, live aircraft data, or cloud credentials.

## Core capabilities

| Capability | Current implementation |
|---|---|
| Guardian | Mock default, opt-in deterministic evidence/state machine |
| Sentinel | Mock default, opt-in deterministic authorization/lifecycle protection |
| Simulator | Five deterministic virtual-time scenarios and independently checked symbolic actions |
| Vision | Mock by default; optional local uncertainty-aware adapter, not medical diagnosis |
| ATC | Fictional approval/rejection controls, referential incident/run validation |
| Frontend | Six React dashboard views, browser-tested and frontend tests passing |
| Event audit | SQLite ordered events and REST history/replay; no claimed SSE stream |
| IBM LinuxONE | Documented optional remote supervisor; no live deployment or target verification |

## Safety invariants

- All telemetry and scenarios are synthetic.
- A blocked camera, missing face, or single closed-eye observation is not evidence of incapacity.
- A responsive second pilot prevents an unsupported dual-pilot conclusion.
- Guardian never directs the simulator.
- Sentinel can request only `NO_OP`, `SIM_HOLD_STATE`, `SIM_STABILIZE`, `SIM_SCRIPTED_DIVERSION`, or `SIM_ABORT`.
- Connected ATC requires a current, matching, affirmative simulated approval.
- ATC disconnection alone never authorizes fallback.
- The simulator independently validates run identity, action, and transition.
- Old-run and duplicate commands cannot repeat side effects.
- No LLM participates in simulation-action approval.

## Architecture

The target stack is Python 3.11, FastAPI, Pydantic v2, SQLite, React, Vite, and TypeScript. One application orchestrator owns module wiring, ordered event dispatch, persistence, and snapshot updates. REST carries commands, snapshots and ordered event history. A replay-safe SSE stream is deferred; do not describe it as operational. Canonical Python models generate OpenAPI, JSON Schema, and frontend TypeScript types.

```text
Mock/optional vision + synthetic simulator + pilot acknowledgements
                              |
                        Orchestrator
                              |
                Guardian -> incident -> Sentinel
                                      /        \
                            simulated ATC   restricted fallback
                                      \        /
                              authorized symbolic action
                                      |
                         SQLite audit -> REST history/polling -> UI
```

See [Architecture](docs/ARCHITECTURE.md), [Contracts](docs/CONTRACTS.md), and [Decisions](docs/DECISIONS.md).

## Repository structure

```text
AEROGUARD_CODEX_MASTER_BOOTSTRAP_V3.md  authoritative specification
AGENTS.md                               coding-agent rules
docs/                                  architecture and team documentation
.github/pull_request_template.md        review checklist
backend/                                FastAPI app, contracts, mocks, store, tests
frontend/                               React/Vite/TypeScript dashboard and tests
contracts/                              validated fixtures and generated contracts
scripts/                                deterministic generation, drift, and smoke tools
```

## Prerequisites, testing, and launch

Requirements: Python 3.11+, Node.js/npm, GNU Make, Git and SQLite support. No IBM credentials or webcam is needed for the default demo.

```bash
git clone https://github.com/rupeshhh007/ibm-flight.git
cd ibm-flight
make setup
make check
make smoke
npm --prefix frontend test
npm --prefix frontend run build
backend/.venv/bin/python -m pytest backend/tests/integration -q
```

If you already have the repo:

```bash
git switch main
git pull --ff-only origin main
npm --prefix frontend ci
```

Start **two terminals** from the repository root:

**Terminal 1 — backend (127.0.0.1:8000):**

```bash
AEROGUARD_AGENT_MODE=deterministic make backend
```

For the frozen mock baseline, use just `make backend` instead.

**Terminal 2 — frontend (127.0.0.1:5173):**

```bash
npm --prefix frontend run dev
```

Open `http://127.0.0.1:5173/`. Backend health: `http://127.0.0.1:8000/healthz`; interactive API: `http://127.0.0.1:8000/docs`. If Vite reports `ECONNREFUSED 127.0.0.1:8000`, start the backend first. Run a single backend worker.

**Dependency advisory:** The October 18 review found 6 vulnerabilities in the full npm development-tool audit (3 moderate, 1 high, 2 critical), with 0 vulnerabilities from `npm --prefix frontend audit --omit=dev`. Do not report these as fixed; upgrades or documented maintainer risk acceptance are still needed. Do not blindly run `npm audit fix --force`.

## Environment variables

`.env.example` defines `AEROGUARD_DATABASE_PATH`, defaulting to `aeroguard.db`. Local databases, virtual environments, caches, `.env` files, and `node_modules` are ignored. No secrets are required for P0.

## Scenario catalogue

The stable target scenario IDs are:

| ID | Expected safety outcome |
|---|---|
| `normal_flight` | No Guardian escalation and no Sentinel action |
| `single_pilot_unresponsive` | Acknowledge/suspicion flow; responsive pilot prevents autonomous action |
| `dual_pilot_atc_connected` | Wait for a valid simulated approval; execute at most one allowed action |
| `dual_pilot_atc_disconnected` | Restricted fallback only after all stronger-evidence prerequisites |
| `camera_obstructed` | `UNKNOWN` observation; no action from obstruction alone |

All five scenario IDs are covered by backend tests; the browser demo has also been exercised against the integrated backend. Not every optional P1 feature, including LinuxONE sync or replay-safe SSE, has been delivered. See [Demo Runbook](docs/DEMO_RUNBOOK.md).

## Target API

P0 implements health/readiness, state and scenario queries, scenario start/advance/reset, pilot acknowledgement, fictional ATC decision, communication-link change, incident history, and bounded event history. Replay-safe `/api/v1/events/stream` is intentionally not claimed; use REST event history and UI polling. Exact models are generated from the live app; see [Contracts](docs/CONTRACTS.md).

## Testing and validation

`make test` executes contract, fixture, Protocol-conformance, clock, scenario, store, API, authorization, idempotency, and old-run tests. `make contracts-check` regenerates to temporary storage and compares artifacts without mutating the tree. `make check` also typechecks the generated TypeScript declaration. `make smoke` runs the connected emergency path and proves rejection/no-action, approval/one action, and duplicate suppression. See [Test Matrix](docs/TEST_MATRIX.md).

## Team

| Developer | Responsibility | Branch |
|---|---|---|
| Tejas | Computer Vision & Pilot Monitoring | `feat/vision` |
| Rohan | Aircraft Telemetry & Flight Simulation | `feat/simulator` |
| Rupesh | Guardian Monitoring Agent | `feat/guardian` |
| Amrit | Sentinel Emergency Response Agent | `feat/sentinel` |
| Tarun | Frontend, Cockpit & ATC UI | `feat/frontend` |
| Abhinav | Backend Integration, IBM LinuxONE & Testing | `feat/platform` |

Rupesh approves architectural decisions; Abhinav is integration lead and post-freeze canonical-contract editor. Detailed path ownership is in [Ownership](docs/OWNERSHIP.md).

## IBM LinuxONE scope

LinuxONE is optional and outside the local safety-critical path. The portable supervisory portion may receive events and support audit/analytics after s390x compatibility and access are verified. It must not host CV dependencies or become required for local action authorization. No deployment or connection currently exists. See [IBM LinuxONE](docs/IBM_LINUXONE.md).

## Known limitations and final submission

- All scenarios and actions are **simulation only**; there is no real aircraft input/control, operational ATC link, or diagnosis.
- The default runtime uses mock modules, with explicit deterministic Guardian/Sentinel opt-in. The optional CV adapter is not operational-grade.
- One-process in-memory state is not fully reconstructed from persisted events after process restart; audit history persists.
- Replay-safe SSE is not shipped; REST event history/polling is the supported path.
- **IBM LinuxONE:** the remote event-sync adapter/intake and actual `s390x` deployment remain unverified and must not be claimed as finished.
- The full npm audit reported six development-tool vulnerabilities; production-only dependency audit reported zero at review time.

**Final checklist:** verify current `main` tests, start backend and frontend together, capture Flight Deck / Scenarios / Sentinel / Black Box screenshots, record the connected dual-pilot approve/reject demonstration, confirm actual IBM Datathon requirements and LinuxONE access, and submit the repository URL plus required artifacts.

## Documentation index

- [Architecture](docs/ARCHITECTURE.md)
- [Contracts](docs/CONTRACTS.md)
- [Ownership](docs/OWNERSHIP.md)
- [Contract change protocol](docs/CONTRACT_CHANGE_PROTOCOL.md)
- [Integration](docs/INTEGRATION.md)
- [Team handoffs](docs/TEAM_HANDOFF.md)
- [Demo runbook](docs/DEMO_RUNBOOK.md)
- [Test matrix](docs/TEST_MATRIX.md)
- [IBM LinuxONE](docs/IBM_LINUXONE.md)
- [Architecture decisions](docs/DECISIONS.md)
- [Blockers](docs/BLOCKERS.md)
- [Master specification](AEROGUARD_CODEX_MASTER_BOOTSTRAP_V3.md)
