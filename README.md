# AeroGuard

> **SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE**

AeroGuard is an IBM Z Datathon project for demonstrating a safe, auditable aviation-emergency simulation. It combines uncertain camera-derived pilot observations, synthetic aircraft telemetry, deterministic incident evaluation, fictional ATC decisions, restricted symbolic simulator actions, and an operator dashboard. It does not connect to aircraft, avionics, operational ATC, or navigation systems.

## Project status

The executable P0 foundation is implemented on `feat/p0-executable-foundation`: strict canonical Pydantic contracts, frozen Python Protocols, five deterministic scenario IDs, replaceable mocks, one FastAPI server/orchestrator, SQLite event and command persistence, generated OpenAPI/JSON Schema/TypeScript contracts, critical safety tests, and a connected-emergency smoke path. P1 remains open for the polished React UI, replay-safe SSE, richer five-scenario behavior, real CV, and LinuxONE deployment.

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

| Capability | Intended behavior | Current status |
|---|---|---|
| Guardian monitoring | Correlate typed observations and acknowledgements | P0 deterministic mock implemented |
| Sentinel response | Gate symbolic actions on incident/run identity and authorization | P0 connected-ATC path implemented |
| Synthetic simulator | Deterministic telemetry and independently validated symbolic actions | P0 implemented |
| Vision adapter | Mock observations by default; optional local OpenCV/MediaPipe adapter | Mock implemented; real CV is P1 |
| Simulated ATC | Fictional approve/reject workflow for the active incident | P0 implemented |
| Dashboard | Cockpit, ATC, simulation, and audit views | P1 |
| Event audit | SQLite ordering and REST history | P0 implemented; SSE is P1 |
| LinuxONE boundary | Optional supervisory event intake/audit/analytics | Conceptual and unverified |

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

The target stack is Python 3.11, FastAPI, Pydantic v2, SQLite, React, Vite, and TypeScript. One application orchestrator owns module wiring, ordered event dispatch, persistence, and snapshot updates. REST carries commands and snapshots; SSE carries committed events with sequence-based replay. Canonical Python models generate OpenAPI, JSON Schema, and frontend TypeScript types.

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
                         SQLite audit -> REST/SSE -> UI
```

See [Architecture](docs/ARCHITECTURE.md), [Contracts](docs/CONTRACTS.md), and [Decisions](docs/DECISIONS.md).

## Repository structure

```text
AEROGUARD_CODEX_MASTER_BOOTSTRAP_V3.md  authoritative specification
AGENTS.md                               coding-agent rules
docs/                                  architecture and team documentation
.github/pull_request_template.md        review checklist
backend/                                FastAPI app, contracts, mocks, store, tests
frontend/                               pinned TypeScript contract-generation package
contracts/                              validated fixtures and generated contracts
scripts/                                deterministic generation, drift, and smoke tools
```

## Prerequisites and setup

Prerequisites are Python 3.11 or newer, Node.js/npm, GNU Make, Git, and SQLite support from Python's standard library. Install into the repository-scoped virtual environment and run the verified P0 workflow:

```text
make setup
make contracts-check
make test
make check
make smoke
```

Run the single-worker backend with `make backend`; it listens at `http://127.0.0.1:8000`. On Windows, use `make PYTHON=python <target>` when `python3` is unavailable. The default mode requires no webcam, IBM connection, or paid API key.

Troubleshooting: install Python 3.11+ if setup rejects the interpreter; install Node/npm if `npm` is missing; install GNU Make or run the displayed underlying commands if `make` is unavailable; stop the conflicting process or select an explicitly reviewed local port if port 8000 is occupied.

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

The normal, single-pilot safety-negative, connected dual-pilot approval, disconnected-no-fallback, and camera-obstruction behaviors are deterministic P0 baselines. Fuller scenario dynamics remain P1. See [Demo Runbook](docs/DEMO_RUNBOOK.md).

## Target API

P0 implements health/readiness, state and scenario queries, scenario start/advance/reset, pilot acknowledgement, fictional ATC decision, communication-link change, incident history, and bounded event history. Replay-safe `/api/v1/events/stream` is intentionally P1 and is not exposed as a placeholder. Exact models are generated from the live app; see [Contracts](docs/CONTRACTS.md).

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

## Known limitations

- The P0 state is held in memory and is not reconstructed after a process restart; SQLite audit events and command results persist.
- P0 has no live SSE endpoint or polished React dashboard.
- Offline automatic fallback is deliberately not implemented; disconnection alone remains a tested no-action condition.
- Scenario dynamics and Guardian evidence fusion are intentionally minimal replaceable baselines.
- LinuxONE access and s390x dependency compatibility are unverified.
- Nothing in this project is suitable for operational aviation use.

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
