# AeroGuard

> **SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE**

AeroGuard is an IBM Z Datathon project for demonstrating a safe, auditable aviation-emergency simulation. It combines uncertain camera-derived pilot observations, synthetic aircraft telemetry, deterministic incident evaluation, fictional ATC decisions, restricted symbolic simulator actions, and an operator dashboard. It does not connect to aircraft, avionics, operational ATC, or navigation systems.

## Project status

This repository currently contains the documentation foundation only. The FastAPI backend, React frontend, canonical Pydantic contracts, generated artifacts, scenarios, tests, and CI described below are **planned and not implemented**. Consequently, neither the P0 launch gate nor P1 baseline gate is satisfied. See [Blockers](docs/BLOCKERS.md) and the [Test Matrix](docs/TEST_MATRIX.md).

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
| Guardian monitoring | Correlate typed observations, telemetry, and acknowledgements | Specified only |
| Sentinel response | Gate symbolic actions on incident/run identity and authorization | Specified only |
| Synthetic simulator | Deterministic telemetry and independently validated symbolic actions | Specified only |
| Vision adapter | Mock observations by default; optional local OpenCV/MediaPipe adapter | Specified only |
| Simulated ATC | Fictional approve/reject workflow for the active incident | Specified only |
| Dashboard | Cockpit, ATC, simulation, and audit views | Specified only |
| Event audit | SQLite ordering, history, replay, and SSE delivery | Specified only |
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
backend/                                planned FastAPI implementation
frontend/                               planned React/Vite implementation
contracts/                              planned fixtures/generated contracts
scripts/                                planned generation and smoke tools
```

## Prerequisites and setup

Planned prerequisites are Python 3.11, Node.js/npm, Git, and a platform with SQLite support. No setup script, dependency manifest, backend, or frontend exists yet. Therefore commands such as `make setup`, `make backend`, `make frontend`, `make dev`, `make test`, and `make smoke` are target commands, not currently runnable commands.

When implementation lands, the intended workflow is:

```text
make setup
make dev
make check
make smoke
```

The planned local backend address is `http://127.0.0.1:8000`; the Vite server will proxy API requests rather than hardcode a deployment host. The default mode must require no webcam, IBM connection, or paid API key.

## Environment variables

No `.env.example` exists yet. Planned configuration includes a local SQLite path, log level, CORS/dev origin, optional remote-sync enablement and URL, and bounded SSE settings. Secrets must never be committed. Exact names will be defined by Abhinav with the backend configuration implementation and then documented here.

## Scenario catalogue

The stable target scenario IDs are:

| ID | Expected safety outcome |
|---|---|
| `normal_flight` | No Guardian escalation and no Sentinel action |
| `single_pilot_unresponsive` | Acknowledge/suspicion flow; responsive pilot prevents autonomous action |
| `dual_pilot_atc_connected` | Wait for a valid simulated approval; execute at most one allowed action |
| `dual_pilot_atc_disconnected` | Restricted fallback only after all stronger-evidence prerequisites |
| `camera_obstructed` | `UNKNOWN` observation; no action from obstruction alone |

These outcomes are specified but have not been verified. See [Demo Runbook](docs/DEMO_RUNBOOK.md).

## Target API

The frozen route names include health/readiness, state and scenario queries, scenario start/advance/reset, pilot acknowledgement, fictional ATC decision, communication-link change, incident history, event history, and event streaming under `/api/v1`. Exact request/response models remain blocked on canonical Pydantic implementation. See [Contracts](docs/CONTRACTS.md).

## Testing and validation

The intended gates cover model validation, event/payload consistency, deterministic state machines, authorization negatives, command deduplication, old-run isolation, ordered persistence, SSE replay, contract drift, frontend build, and mock end-to-end operation. No executable test suite exists today. See [Test Matrix](docs/TEST_MATRIX.md).

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

- Documentation exists before implementation.
- Public Protocol signatures and concrete schemas cannot be frozen until source models exist.
- No API, UI, event store, generated artifacts, scenarios, automated tests, or CI has been verified.
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
