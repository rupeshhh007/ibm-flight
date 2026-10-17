# AeroGuard Canonical Contracts

## Status and authority

This document records the master specification's required v1 contract. There is currently no `backend/app/contracts/` implementation, live FastAPI OpenAPI document, JSON Schema, or generated TypeScript output. Therefore enum literals, route names, required model names, and required fields below are normative requirements, while Python Protocol signatures and unresolved request/response details are explicitly **pending implementation**. They must be copied here from source after implementation, never invented in documentation.

Wire field names use `snake_case`. UUIDs use canonical string form. Datetimes must be timezone-aware UTC ISO 8601 values; the implementation must normalize them to UTC and reject naive timestamps. Unknown enum values and extra fields should be rejected at canonical boundaries.

## Event envelope

### `DomainEvent`

| Field | Type | Rule |
|---|---|---|
| `event_id` | UUID | Unique and immutable |
| `schema_version` | literal `"1.0"` | Frozen initial version |
| `event_type` | `EventType` | Must match the payload variant |
| `occurred_at` | aware UTC datetime | Source/domain time, not database order |
| `source` | `EventSource` | Strict enum; exact values pending canonical source |
| `scenario_run_id` | UUID | Identifies one scenario execution |
| `correlation_id` | UUID | Relates a command/workflow |
| `causation_event_id` | UUID or null | The direct cause when applicable |
| `payload` | discriminated typed payload union | No untyped catch-all dictionary |

### `StoredEvent`

`StoredEvent` contains every `DomainEvent` field plus `seq`, a positive integer assigned by SQLite. `seq` is globally increasing in one local store, determines committed event order, and is the SSE `id`. `occurred_at` must never be used as a replacement for commit order.

The implementation must enforce `event_type` and payload compatibility, preferably with a discriminated union. A `TELEMETRY_UPDATED` envelope carrying a pilot-observation payload, for example, is invalid.

## Required event types

The frozen set is:

| EventType |
|---|
| `SCENARIO_STARTED` |
| `SCENARIO_ADVANCED` |
| `PILOT_OBSERVATION` |
| `TELEMETRY_UPDATED` |
| `PILOT_ACKNOWLEDGED` |
| `ATC_LINK_CHANGED` |
| `GUARDIAN_INCIDENT` |
| `ATC_DECISION` |
| `SENTINEL_DECISION` |
| `SIMULATOR_ACTION` |
| `SCENARIO_RESET` |
| `SCENARIO_COMPLETED` |

No additional event type may be introduced after freeze without the contract-change process. `EventSource` values have not been fixed by source code; Abhinav must define the minimum explicit sources during canonical-model implementation and update this table from code.

## Required payload and domain models

### `PilotObservation`

| Field | Type/rule |
|---|---|
| `pilot_id` | `PILOT_1` or `PILOT_2` |
| `observed_at` | aware UTC datetime |
| `observation_status` | `RESPONSIVE`, `POSSIBLY_UNRESPONSIVE`, or `UNKNOWN` |
| `camera_available` | boolean |
| `face_visible` | boolean |
| `eyes_closed` | boolean |
| `observation_duration_ms` | non-negative bounded integer; exact upper bound pending source |
| `observation_quality` | number from 0 through 1 inclusive |

If the camera is unavailable or evidence unusable, status is `UNKNOWN`. Missing face, obstruction, or a single closed-eye reading is not proof of incapacity.

### `AircraftTelemetry`

Fields: `aircraft_id`, `simulation_time`, `altitude_ft`, `airspeed_kts`, `heading_deg`, `latitude`, `longitude`, `flight_phase`, and `active_warning_codes`. All values are synthetic. Canonical source must document numeric bounds: non-negative reasonable altitude/airspeed ranges, heading normalized to a documented interval, latitude `-90..90`, longitude `-180..180`, and bounded code lengths. Exact `flight_phase` values are pending source and cannot be finalized here.

### `PilotAcknowledgement`

Fields: `command_id: UUID`, `scenario_run_id: UUID`, `pilot_id`, `alert_id`, and aware UTC `acknowledged_at`. Run and alert must be active; duplicate `command_id` cannot repeat a transition.

### `GuardianIncident`

Fields: `incident_id`, `incident_type`, `severity`, `guardian_state`, `evidence_event_ids`, `explanation`, `acknowledgement_required`, and aware UTC `created_at`. Evidence IDs must refer to the active run. The explanation records the exact deterministic rule/threshold. Exact incident/severity enum values are pending canonical source.

### `ATCDecision`

Fields: `command_id: UUID`, `scenario_run_id: UUID`, `incident_id`, `decision` (`APPROVE` or `REJECT`), `requested_action`, `operator_id`, and aware UTC `issued_at`. Approval is valid only for the active incident/run and an allowed action; rejection is never authorization.

### `SentinelDecision`

Fields: `decision_id`, `incident_id`, `scenario_run_id`, `sentinel_state`, `action_type`, `authorization_source`, `reason`, `evidence_event_ids`, aware UTC `executed_at`, and `result`. Exact authorization/result enum values are pending source. The record must distinguish approved, rejected, duplicate, stale, and failed simulator outcomes.

### `CommunicationStatus`

Fields: `atc_link_connected`, aware UTC `last_change_at`, `remote_sync_connected`, and non-negative `pending_sync_count`. The ATC flag is a simulated scenario input, browser/server connectivity is transport state, and remote sync is optional integration state; they are not interchangeable.

### `SystemSnapshot`

Contains active `scenario_id`, `scenario_run_id`, virtual-time value, both pilot states, current telemetry, Guardian state, Sentinel state, active incident, simulated ATC link, last permitted simulator action, `latest_event_seq`, and clear demo status text. Exact nested types and nullability are pending canonical source. Snapshot state must agree with stored decisions.

### API models

Canonical source must provide `CommonApiError`, scenario start/advance/reset requests and responses, ATC/link/ack command requests and responses, and typed list/pagination responses. `CommonApiError` must consistently expose a stable machine code, human-readable message, and structured validation/context details without leaking internals; exact fields await source implementation.

## State and action enums

### Guardian

`NORMAL`, `SUSPECTED`, `AWAITING_ACK`, `ESCALATED`, `RECOVERING`

| From | To | Minimum target condition |
|---|---|---|
| `NORMAL` | `SUSPECTED` | Current-run usable concern evidence |
| `SUSPECTED` | `AWAITING_ACK` | Alert issued under configured deterministic rule |
| `SUSPECTED`/`AWAITING_ACK` | `ESCALATED` | Repeated usable evidence plus missed acknowledgement and supporting conditions; responsive peer blocks dual claim |
| Concern states | `RECOVERING` | Valid acknowledgement or sufficient responsive evidence |
| `RECOVERING` | `NORMAL` | Documented recovery condition |
| Any | initial `NORMAL` | New run/reset; old-run evidence excluded |

This table is the required behavioral floor, not a complete machine definition. Exact thresholds and allowed edges must be machine-readable/tested in source before freeze.

### Sentinel

`STANDBY`, `AWAITING_ATC`, `LOCAL_FALLBACK`, `SIM_ACTION_RUNNING`, `COMPLETED`, `ABORTED`

| From | To | Minimum target condition |
|---|---|---|
| `STANDBY` | `AWAITING_ATC` | Current-run verified escalation while simulated ATC is connected |
| `STANDBY` | `LOCAL_FALLBACK` | Current-run escalation plus all stronger disconnected prerequisites; disconnection alone is insufficient |
| `AWAITING_ATC` | `SIM_ACTION_RUNNING` | Fresh matching `APPROVE` for allowed action |
| `LOCAL_FALLBACK` | `SIM_ACTION_RUNNING` | Restricted scripted fallback authorized by deterministic rule |
| `SIM_ACTION_RUNNING` | `COMPLETED` | Simulator validates and reports completion |
| Waiting/running states | `ABORTED` | Rejection, invalidation, explicit abort, or documented failure path |
| Any | initial `STANDBY` | New run/reset; old-run inputs excluded |

Every invalid transition is rejected predictably and audited.

### Allowed symbolic simulator actions

`NO_OP`, `SIM_HOLD_STATE`, `SIM_STABILIZE`, `SIM_SCRIPTED_DIVERSION`, `SIM_ABORT`

They have no mapping to operational avionics, navigation, flight surfaces, or real aircraft control. The simulator validates the enum, active run, deduplication state, and permitted transition independently of Sentinel.

## Public module Protocols

The following public boundaries are required:

| Protocol | Required capability | Signature status |
|---|---|---|
| `VisionAdapter` | Produce validated observation(s); support deterministic mock | Pending `backend/app/contracts/interfaces.py` |
| `AircraftSimulator` | Start/reset/advance a scenario; apply permitted action; return typed state | Pending source |
| `GuardianAgent` | Consume typed events; expose typed state/incident; emit typed events | Pending source |
| `SentinelAgent` | Consume incident/ATC/link inputs; expose typed state; emit decisions/action requests | Pending source |
| `EventStore` | Atomic ordered append; read after sequence; fetch snapshot/history | Pending source |
| `EventPublisher` | Publish committed stored events to live subscribers | Pending source |
| `Clock` | Return/advance virtual time without sleeping | Pending source |
| `RemoteSyncAdapter` | Optional mockable supervisory sync | Pending source |

No Python method signature is presented because no implementation exists. This is a launch blocker. Abhinav must implement strict Protocols plus conforming mocks/tests, then replace “Pending source” with exact definitions copied from source. Feature developers must inspect those definitions directly before coding.

## REST API route contract

These route names and methods are frozen targets:

| Method | Path | Purpose | Model status |
|---|---|---|---|
| GET | `/healthz` | Process liveness | Pending source |
| GET | `/readyz` | Local dependency readiness | Pending source |
| GET | `/api/v1/state` | Current typed snapshot | `SystemSnapshot` required; wrapper pending |
| GET | `/api/v1/scenarios` | Stable scenario catalogue | Response pending |
| POST | `/api/v1/scenarios/start` | Start selected scenario; create new run | Request/response pending |
| POST | `/api/v1/scenarios/advance` | Advance bounded virtual `delta_ms`, inclusive at boundary | Request/response pending |
| POST | `/api/v1/scenarios/reset` | Reset identified active run; retain history; create new run identity as documented | Request/response pending |
| POST | `/api/v1/pilots/acknowledge` | Submit active-run pilot acknowledgement | Required model fields defined above |
| POST | `/api/v1/atc/decision` | Submit fictional ATC approve/reject command | `ATCDecision` fields defined above |
| POST | `/api/v1/communications/link` | Change simulated ATC-link state | Request/response pending |
| GET | `/api/v1/incidents` | Typed incident list | Pagination model pending |
| GET | `/api/v1/events?after_seq=0&limit=100` | Ordered committed event history | Bounded `limit`; list model pending |
| GET | `/api/v1/events/stream?after_seq=0` | Replay-safe SSE stream | SSE data is `StoredEvent` |

Mutations require `command_id`; current-run identity is required where applicable. Start accepts a command ID and returns the new run ID. Reset must state which active run is being reset. Replays return the original/same documented result and never repeat effects. The live OpenAPI document becomes authoritative for exact body/response shapes once implemented.

## Scenario run identity and command deduplication

A new start/reset creates a new `scenario_run_id`. All domain inputs must be checked against the active run before state mutation. Historical events remain readable but cannot re-enter active processing. SQLite uniqueness must prevent duplicate `event_id` and `command_id`; the command-result record or equivalent must allow idempotent retry responses. An identical ID with a conflicting body must be rejected and audited, not treated as a valid retry.

## SSE contract

Each SSE item uses the persisted `seq` as `id`, a stable event name derived from `event_type`, and serialized `StoredEvent` JSON as data. Clients reconnect with `Last-Event-ID` or `after_seq`, accept only strictly increasing sequences, and can recover through REST. The server must eliminate the replay/live gap with a subscription/high-water-mark or equivalent serialized design. Keepalive format and queue bounds await implementation.

## Generated artifacts and versioning

Planned generated files are `contracts/generated/openapi.json`, event JSON Schemas under `contracts/generated/events/`, and TypeScript output under `frontend/src/api/generated/`. `make contracts` regenerates them deterministically; `make contracts-check` generates to temporary storage and compares without changing the worktree. Generator versions must be pinned. Fixtures in `contracts/fixtures/` must validate against canonical models. None of these assets or commands exists yet.

Contract version `1.0` is frozen after bootstrap. Changes follow [Contract Change Protocol](CONTRACT_CHANGE_PROTOCOL.md), regenerate all artifacts, update this document from source, and add regression/fixture coverage.
