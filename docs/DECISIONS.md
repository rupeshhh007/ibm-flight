# AeroGuard Architecture Decision Log

Entries identify both architectural acceptance and current implementation evidence.

## ADR-001: Python 3.11, FastAPI, and Pydantic v2

- **Context:** The project needs a quickly implemented typed HTTP API and one source for runtime validation/OpenAPI.
- **Decision:** Use Python 3.11, FastAPI, and strict Pydantic v2 models.
- **Rationale:** Strong validation and schema generation reduce six-branch contract drift.
- **Tradeoffs:** Version pinning and generated-artifact discipline are required.
- **Consequences:** Backend and schema generation must boot without optional CV libraries.
- **Status:** Implemented and verified in the P0 backend.

## ADR-002: React, Vite, and TypeScript

- **Context:** The demo needs a responsive cockpit/ATC/scenario UI.
- **Decision:** Use React with Vite and TypeScript, consuming generated API types.
- **Tradeoffs:** A Node toolchain is required, but fast development and static checking suit the event dashboard.
- **Status:** TypeScript generation/typecheck implemented; React/Vite application remains P1.

## ADR-003: SQLite append-only event store

- **Context:** Ordered local audit and replay are required without infrastructure.
- **Decision:** Use SQLite with global sequence IDs, unique event/command identities, and retained history across resets.
- **Tradeoffs:** Excellent local simplicity; not intended for multi-writer horizontal scale.
- **Status:** Implemented and verified for ordered events and command results; snapshot reconstruction is not claimed.

## ADR-004: One orchestrator and one serialized mutation path

- **Context:** Independent modules must not race or wire each other privately.
- **Decision:** A single composition root owns dispatch, state mutation, persistence order, snapshot updates, and publication in a single-worker process.
- **Consequences:** No multiple Uvicorn workers with independent memory; camera work stays off the event loop.
- **Status:** Implemented with one process, one orchestrator, and a re-entrant application lock.

## ADR-005: Typed versioned events

- **Context:** Untyped dictionaries invite payload/event mismatches.
- **Decision:** Use a strict `1.0` event schema with a discriminated payload union and enforce event-type compatibility.
- **Tradeoffs:** Adding fields or event kinds requires the contract-change process.
- **Status:** Implemented with `DomainEvent`/`StoredEvent` and event-type/payload validation.

## ADR-006: Deterministic virtual clock

- **Context:** Real-time sleeps are slow and nondeterministic.
- **Decision:** All scenario/domain time comes from an injected clock advanced by bounded milliseconds; boundary events are intended to be inclusive.
- **Status:** Implemented and boundary-tested with inclusive scheduled events.

## ADR-007: REST plus SSE

- **Context:** Commands/snapshots fit request-response while events need incremental delivery.
- **Decision:** Use REST for commands, snapshots, and history; use replay-safe SSE for committed events. REST polling is the P0 fallback.
- **Tradeoffs:** SSE requires careful replay/live handoff and bounded queues.
- **Status:** REST commands/snapshot/history implemented; replay-safe SSE remains P1 and is not exposed as a placeholder.

## ADR-008: Generated contracts

- **Context:** Handwritten Python and TypeScript models drift.
- **Decision:** Generate OpenAPI from the live app, JSON Schema from canonical Pydantic models, and TypeScript types from OpenAPI. CI compares deterministic output.
- **Status:** Implemented with deterministic temporary drift comparison.

## ADR-009: Local mocks are the default

- **Context:** Webcam, network, credentials, and hardware cannot be datathon prerequisites.
- **Decision:** Deterministic mock vision, synthetic scenarios, and mock remote sync must support the complete local path.
- **Tradeoffs:** Mocks demonstrate contracts and safety, not production accuracy.
- **Status:** Implemented; mock/no-webcam/no-IBM smoke path verified.

## ADR-010: Restricted symbolic actions

- **Context:** The demo must not resemble operational aircraft control.
- **Decision:** Sentinel may request only the five frozen symbolic actions, and the simulator independently validates them. No LLM may authorize an action.
- **Status:** Implemented and safety-tested for the connected simulated-ATC path.

## ADR-011: Optional LinuxONE supervision

- **Context:** IBM Z relevance is desired without making remote availability safety-critical.
- **Decision:** LinuxONE may receive events and provide audit/analytics; it is outside local authorization and must be s390x-compatible.
- **Status:** Accepted concept; access/deployment unverified.

## ADR-012: Exclude distributed infrastructure

- **Context:** Redis, Kafka, Celery, Kubernetes, multi-backend designs, and agent frameworks add integration risk during a 24-hour event.
- **Decision:** Exclude them from the initial architecture.
- **Consequences:** Scale is deliberately traded for clarity and reliable local execution.
- **Status:** Accepted.
