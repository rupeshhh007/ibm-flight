# AeroGuard Canonical Contracts

## Status and authority

This document records the implemented v1 contract in `backend/app/contracts/`. The live FastAPI application generates `contracts/generated/openapi.json`, event JSON Schemas, and `frontend/src/api/generated/schema.d.ts`. The source models and Protocols are authoritative; generated files are never edited manually.

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

No additional event type may be introduced after freeze without the contract-change process. `EventSource` is frozen as `SYSTEM`, `SCENARIO`, `VISION`, `SIMULATOR`, `GUARDIAN`, `SENTINEL`, `PILOT`, and `SIMULATED_ATC`.

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
| `observation_duration_ms` | integer from `0..600000` inclusive |
| `observation_quality` | number from 0 through 1 inclusive |

If the camera is unavailable or evidence unusable, status is `UNKNOWN`. Missing face, obstruction, or a single closed-eye reading is not proof of incapacity.

### `AircraftTelemetry`

Fields: `aircraft_id`, `simulation_time`, `altitude_ft`, `airspeed_kts`, `heading_deg`, `latitude`, `longitude`, `flight_phase`, and `active_warning_codes`. All values are synthetic. Bounds are altitude `-1500..70000`, airspeed `0..800`, heading `0 <= value < 360`, latitude `-90..90`, longitude `-180..180`, at most 32 warning codes, and identifiers/codes of at most 64 characters. `FlightPhase` is `PREFLIGHT`, `CRUISE`, `DESCENT`, or `COMPLETED`.

### `PilotAcknowledgement`

Fields: `command_id: UUID`, `scenario_run_id: UUID`, `pilot_id`, `alert_id`, and aware UTC `acknowledged_at`. Run and alert must be active; duplicate `command_id` cannot repeat a transition.

### `GuardianIncident`

Fields: `incident_id`, `scenario_run_id`, `incident_type`, `severity`, `guardian_state`, `evidence_event_ids`, `explanation`, `acknowledgement_required`, and aware UTC `created_at`. `IncidentType` is `PILOT_RESPONSE_REQUIRED` or `DUAL_PILOT_UNRESPONSIVE`; severity is `WARNING` or `CRITICAL`. Evidence IDs must refer to the active run. The explanation records the exact deterministic rule/threshold.

### `ATCDecision`

Fields: `command_id: UUID`, `scenario_run_id: UUID`, `incident_id`, `decision` (`APPROVE` or `REJECT`), `requested_action`, `operator_id`, and aware UTC `issued_at`. Approval is valid only for the active incident/run and an allowed action; rejection is never authorization.

### `SentinelDecision`

Fields: `decision_id`, `incident_id`, `scenario_run_id`, `sentinel_state`, `action_type`, `authorization_source`, `reason`, `evidence_event_ids`, aware UTC `executed_at`, and `result`. `AuthorizationSource` is `NONE`, `SIMULATED_ATC`, or `LOCAL_FALLBACK`; `DecisionResult` is `PENDING`, `APPROVED`, `REJECTED`, `EXECUTED`, or `FAILED`. Duplicate and stale commands are rejected by orchestration before another side effect.

### `CommunicationStatus`

Fields: `atc_link_connected`, aware UTC `last_change_at`, `remote_sync_connected`, and non-negative `pending_sync_count`. The ATC flag is a simulated scenario input, browser/server connectivity is transport state, and remote sync is optional integration state; they are not interchangeable.

### `SystemSnapshot`

Contains active `scenario_id`, `scenario_run_id`, virtual-time value, both pilot states, current telemetry, Guardian state, Sentinel state, active incident, simulated ATC link, last permitted simulator action, `latest_event_seq`, and clear demo status text. Exact nested types and nullability are pending canonical source. Snapshot state must agree with stored decisions.

### API models

Implemented API models are `ScenarioStartRequest`, `ScenarioAdvanceRequest`, `ScenarioResetRequest`, `PilotAcknowledgement`, `ATCDecision`, `CommunicationLinkRequest`, `CommandResponse`, `ScenarioListResponse`, `EventHistoryResponse`, `IncidentListResponse`, `HealthResponse`, and `CommonApiError`. `CommonApiError` contains `code`, `message`, and `details: list[str]` without internal exception data.

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

These exact signatures are frozen in `backend/app/contracts/interfaces.py`:

```python
class VisionAdapter(Protocol):
    def configure_scenario(self, scenario_id: str) -> None: ...
    def observe(self, pilot_id: PilotId, observed_at: datetime) -> PilotObservation: ...

class AircraftSimulator(Protocol):
    def start(self, scenario_run_id: UUID, scenario_id: str, started_at: datetime) -> AircraftTelemetry: ...
    def advance(self, scenario_run_id: UUID, simulation_time: datetime) -> AircraftTelemetry: ...
    def apply_action(self, scenario_run_id: UUID, action: SimulatorActionType,
                     authorization: SentinelDecision, applied_at: datetime) -> SimulatorActionPayload: ...
    def reset(self, scenario_run_id: UUID, scenario_id: str, reset_at: datetime) -> AircraftTelemetry: ...

class GuardianAgent(Protocol):
    @property
    def state(self) -> GuardianState: ...
    @property
    def active_incident(self) -> GuardianIncident | None: ...
    def reset(self, scenario_run_id: UUID) -> None: ...
    def consume_observation(self, event: StoredEvent) -> GuardianIncident | None: ...
    def acknowledge(self, acknowledgement: PilotAcknowledgement) -> None: ...

class SentinelAgent(Protocol):
    @property
    def state(self) -> SentinelState: ...
    def reset(self, scenario_run_id: UUID, atc_connected: bool) -> None: ...
    def on_incident(self, incident: GuardianIncident, observed_at: datetime) -> SentinelDecision: ...
    def decide(self, decision: ATCDecision) -> SentinelDecision: ...
    def set_atc_link(self, scenario_run_id: UUID, connected: bool) -> None: ...
    def complete_action(self) -> None: ...

class EventStore(Protocol):
    def append(self, events: Sequence[DomainEvent]) -> list[StoredEvent]: ...
    def read_after(self, after_seq: int, limit: int) -> list[StoredEvent]: ...
    def latest_seq(self) -> int: ...
    def get_command(self, command_id: UUID) -> CommandRecord | None: ...
    def record_command(self, record: CommandRecord) -> None: ...
    def close(self) -> None: ...

class EventPublisher(Protocol):
    def publish(self, events: Sequence[StoredEvent]) -> None: ...

class Clock(Protocol):
    def now(self) -> datetime: ...
    def advance(self, delta_ms: int) -> datetime: ...

class RemoteSyncAdapter(Protocol):
    def sync(self, events: Sequence[StoredEvent]) -> int: ...
```

Runtime-conformance tests cover the core mock implementations. The orchestrator imports these interfaces rather than feature-private classes.

## REST API route contract

These route names and methods are frozen targets:

| Method | Path | Purpose | Model status |
|---|---|---|---|
| GET | `/healthz` | Process liveness | `HealthResponse(status="ok")` |
| GET | `/readyz` | SQLite/local readiness | `HealthResponse(status="ready")` |
| GET | `/api/v1/state` | Current typed snapshot | `SystemSnapshot` |
| GET | `/api/v1/scenarios` | Stable scenario catalogue | `ScenarioListResponse` |
| POST | `/api/v1/scenarios/start` | Start selected scenario; create new run | `ScenarioStartRequest` → `CommandResponse` |
| POST | `/api/v1/scenarios/advance` | Advance bounded virtual `delta_ms`, inclusive at boundary | `ScenarioAdvanceRequest` → `CommandResponse` |
| POST | `/api/v1/scenarios/reset` | Reset identified active run; retain history; create new run identity | `ScenarioResetRequest` → `CommandResponse` |
| POST | `/api/v1/pilots/acknowledge` | Submit active-run pilot acknowledgement | `PilotAcknowledgement` → `CommandResponse` |
| POST | `/api/v1/atc/decision` | Submit fictional ATC approve/reject command | `ATCDecision` → `CommandResponse` |
| POST | `/api/v1/communications/link` | Change simulated ATC-link state | `CommunicationLinkRequest` → `CommandResponse` |
| GET | `/api/v1/incidents` | Typed incident list | `IncidentListResponse` |
| GET | `/api/v1/events?after_seq=0&limit=100` | Ordered committed event history | `EventHistoryResponse`; limit `1..500` |
| GET | `/api/v1/events/stream` | Replay-safe SSE stream | P1; deliberately not registered at P0 |

Mutations require `command_id`; current-run identity is required where applicable. Start accepts a command ID and returns the new run ID. Reset identifies the active run being reset and returns a new run identity. Identical replays return the recorded result with `duplicate=true` and never repeat effects; a reused ID with a different body returns `COMMAND_ID_CONFLICT`. The generated live OpenAPI document is authoritative for exact body/response shapes.

### Exact command bodies and response

| Model | Fields |
|---|---|
| `ScenarioStartRequest` | `command_id: UUID`, `scenario_id: str` |
| `ScenarioAdvanceRequest` | `command_id: UUID`, `scenario_run_id: UUID`, `delta_ms: int` (`1..600000`) |
| `ScenarioResetRequest` | `command_id: UUID`, `scenario_run_id: UUID` |
| `PilotAcknowledgement` | `command_id`, `scenario_run_id`, `pilot_id`, `alert_id`, `acknowledged_at` |
| `ATCDecision` | `command_id`, `scenario_run_id`, `incident_id`, `decision`, `requested_action`, `operator_id`, `issued_at` |
| `CommunicationLinkRequest` | `command_id`, `scenario_run_id`, `atc_link_connected`, `changed_at` |
| `CommandResponse` | `command_id`, `accepted`, `duplicate`, `message`, `snapshot: SystemSnapshot`, `events: list[StoredEvent]` |

Example scenario start request:

```json
{
  "command_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "scenario_id": "dual_pilot_atc_connected"
}
```

Example simulated approval body (IDs must come from the active snapshot/incident):

```json
{
  "command_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  "scenario_run_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  "incident_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
  "decision": "APPROVE",
  "requested_action": "SIM_STABILIZE",
  "operator_id": "fictional-atc-demo",
  "issued_at": "2026-01-01T00:00:03Z"
}
```

The API returns `CommonApiError` for failures. Implemented stable codes are `VALIDATION_ERROR` (422), `UNKNOWN_SCENARIO` (404), `NO_ACTIVE_SCENARIO`, `STALE_SCENARIO_RUN`, `COMMAND_ID_CONFLICT`, `NO_ACTIVE_INCIDENT`, `INCIDENT_MISMATCH`, `AUTHORIZATION_REJECTED`, and `SIMULATOR_REJECTED` (409), plus `NO_SCENARIO_RUNNER` (500). Validation or rejected commands do not intentionally mutate active state.

## Scenario run identity and command deduplication

A new start/reset creates a new `scenario_run_id`. All domain inputs must be checked against the active run before state mutation. Historical events remain readable but cannot re-enter active processing. SQLite uniqueness must prevent duplicate `event_id` and `command_id`; the command-result record or equivalent must allow idempotent retry responses. An identical ID with a conflicting body must be rejected and audited, not treated as a valid retry.

## SSE contract

Each SSE item uses the persisted `seq` as `id`, a stable event name derived from `event_type`, and serialized `StoredEvent` JSON as data. Clients reconnect with `Last-Event-ID` or `after_seq`, accept only strictly increasing sequences, and can recover through REST. The server must eliminate the replay/live gap with a subscription/high-water-mark or equivalent serialized design. Keepalive format and queue bounds await implementation.

## Generated artifacts and versioning

Generated files are `contracts/generated/openapi.json`, per-event payload plus envelope JSON Schemas under `contracts/generated/events/`, and `frontend/src/api/generated/schema.d.ts`. `make contracts` regenerates them deterministically; `make contracts-check` generates to temporary storage and compares without changing the worktree. `openapi-typescript` and TypeScript are pinned in `frontend/package-lock.json`. Fixtures in `contracts/fixtures/` validate against canonical models.

Contract version `1.0` is frozen after bootstrap. Changes follow [Contract Change Protocol](CONTRACT_CHANGE_PROTOCOL.md), regenerate all artifacts, update this document from source, and add regression/fixture coverage.
