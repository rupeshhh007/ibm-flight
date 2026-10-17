# AeroGuard Test Matrix

## Status

The P0 suite is executable under `backend/tests/`; the status column reflects local verification on `feat/p0-executable-foundation`. The aggregate commands are `make test`, `make contracts-check`, `make check`, and `make smoke`. P1 rows remain open.

| ID | Module | Objective | Test input | Expected result | Priority | Type | Status |
|---|---|---|---|---|---|---|---|
| CON-001 | Contracts | Validate representative canonical models | Valid fixture per model | Strict parse and normalized UTC output | P0 | Contract | Verified: `test_contracts.py` |
| CON-002 | Events | Reject event/payload mismatch | `TELEMETRY_UPDATED` with observation payload | Validation failure using common error semantics | P0 | Negative contract | Verified: `test_contracts.py` |
| CON-003 | Contracts | Reject invalid UUID, naive time, enum, and bounds | Malformed fields and quality outside `0..1` | Deterministic validation errors | P0 | Negative contract | Verified: `test_contracts.py` |
| VIS-001 | Vision | Camera obstruction remains uncertain | unavailable camera/hidden face | `UNKNOWN`; no incapacity assertion | P0 | Unit/safety | Verified: `test_api_safety.py` |
| VIS-002 | Vision | Validate bounded observation quality/duration | Boundary and out-of-range values | Boundaries accepted; invalid values rejected | P0 | Unit | Verified: `test_contracts.py` |
| GUA-001 | Guardian | Normal observations keep normal state | Responsive observations and nominal telemetry | `NORMAL`; no incident | P0 | Unit | Verified: `test_api_safety.py` |
| GUA-002 | Guardian | Single concern requests acknowledgement only | One pilot possibly unresponsive | Suspicion/ack flow; no dual claim/action | P0 | Unit/safety | Verified: `test_api_safety.py` |
| GUA-003 | Guardian | Responsive peer blocks dual-incapacity action | Concern for pilot 1; responsive pilot 2 | No dual escalation that can authorize action | P0 | Negative safety | Verified: `test_api_safety.py` |
| GUA-004 | Guardian | Evidence/rule is auditable | Repeated qualifying evidence and missed ack | Incident contains current-run IDs and exact rule | P0 | Unit | Verified: `test_api_safety.py` |
| GUA-005 | Guardian | Recovery is explicit | Valid ack | `RECOVERING` and incident cleared | P0 | Unit | Verified P0 recovery: `test_api_safety.py` |
| SEN-001 | Sentinel | Connected path waits for approval | Active escalation; link connected | `AWAITING_ATC`; no simulator action | P0 | Negative safety | Verified: API/smoke |
| SEN-002 | Sentinel | Reject decision cannot authorize | Matching `REJECT` | Audited rejection; no action | P0 | Negative safety | Verified: API/smoke |
| SEN-003 | Sentinel | Reject mismatched/stale approval | Wrong incident or old run | Audited rejection; no action | P0 | Negative safety | Verified: `test_api_safety.py` |
| SEN-004 | Sentinel | Duplicate approval is idempotent | Repeat same `command_id` | Original response/no second action | P0 | Negative safety | Verified: API/smoke |
| SEN-005 | Sentinel | Disconnect toggle alone cannot act | Link changed to disconnected only | No fallback and no action | P0 | Negative safety | Verified: `test_api_safety.py` |
| SEN-006 | Sentinel | Fallback requires every prerequisite | Omit each stronger-evidence prerequisite in turn | No action; reason identifies failed gate | P1 | Negative safety | Partial P0: disconnect-only verified; full matrix pending |
| SEN-007 | Sentinel | Valid fallback is restricted | All current-run prerequisites | Exactly one permitted scripted symbolic action | P1 | Integration | Not implemented; offline positive path is P1 |
| SIM-001 | Simulator | Reject unauthorized enum/action | Unknown or disallowed input | Predictable rejection; no state change | P0 | Negative unit | Verified: `test_simulator_authorization.py` |
| SIM-002 | Simulator | Validate run and transition independently | Old run or invalid transition | Rejection even if caller requested action | P0 | Negative unit | Verified: API/reset/simulator tests |
| CLK-001 | Clock | Advance deterministically without sleep | Bounded `delta_ms` values | Exact inclusive virtual-time boundary processing | P0 | Unit | Verified: `test_clock_and_scenarios.py` |
| SCN-001 | Scenarios | Stable catalogue | List scenarios | Exactly five frozen IDs | P0 | Contract | Verified: `test_clock_and_scenarios.py` |
| SCN-002 | Scenarios | Deterministic replay | Same scenario/advance sequence twice | Equivalent domain outcomes aside from generated IDs | P0 | Scenario | Verified: `test_api_safety.py` |
| SCN-003 | Reset | Isolate old run without deleting audit | Reset then issue old-run command | New run unchanged; old history queryable | P0 | Integration/safety | Verified: `test_api_safety.py` |
| API-001 | API | Health and state are typed | GET health/readiness/state | Documented statuses and valid response models | P0 | API | Verified: API tests and real HTTP probe |
| API-002 | API | Invalid body uses common error | Bad enum/UUID/time | Stable `CommonApiError`; no mutation | P0 | Negative API | Verified: `test_api_safety.py` |
| API-003 | API | Pagination is bounded | Negative/zero/excessive `limit` | Deterministic reject or documented clamp | P0 | Negative API | Verified: `test_api_safety.py` |
| STO-001 | Event store | Sequence is ordered and persistent | Append batch, restart/read after seq | Unique strictly increasing sequence; no skip | P0 | Persistence | Verified: `test_event_store.py` |
| STO-002 | Event store | Event and command IDs deduplicate | Duplicate identifiers | No duplicate commit/effect | P0 | Negative persistence | Verified: store/API/smoke tests |
| SSE-001 | SSE | Replay/live handoff has no gap | Commit during subscriber join | Every committed seq delivered once after client dedup | P1 | Concurrency integration | Not implemented |
| SSE-002 | SSE | Reconnect and ordering | `Last-Event-ID`, duplicate/out-of-order delivery | Client applies only new increasing seq | P1 | Integration | Not implemented |
| SSE-003 | SSE | Bound queue and cleanup | Slow/disconnected subscriber | Bounded resource use and clean disconnect | P1 | Reliability | Not implemented |
| FE-001 | Frontend | Generated API compatibility | Generated declaration typecheck | No handwritten duplicate response models or TS errors | P0 contract/P1 UI | Frontend contract typecheck verified; application pending |
| FE-002 | Frontend | Errors/loading/status are visible | API failure and empty state | Safe status banner; controls do not fake success | P1 | Frontend | Not implemented |
| GEN-001 | Codegen | Detect generated drift | Controlled stale temporary artifact | `make contracts-check` compares without mutation; comparator fails stale fixture | P0 | Build/contract | Verified: drift test and `make contracts-check` |
| E2E-001 | Full mock | Normal flight end to end | Start/advance `normal_flight` | Stored ordered events; no incident/action | P0 | End-to-end | Verified: `test_api_safety.py` |
| E2E-002 | Full mock | Connected approval gate | Connected dual scenario, approve once | Nothing before approval; one allowed action after | P0 | End-to-end | Verified: API test and `make smoke` |
| E2E-003 | Full mock | Camera obstruction safety | `camera_obstructed` | `UNKNOWN`; no action from obstruction | P0 | End-to-end | Verified: `test_api_safety.py` |
| IBM-001 | Remote sync | Local operation survives remote failure | Mock timeout/disconnect/backlog | Local path continues; pending count/audit updates | P1 | Integration | Not implemented |
| IBM-002 | LinuxONE | Verify actual target compatibility | s390x environment, dependency install, intake probe | Evidence-backed result; no x86-only claim | P1/optional | Deployment | Not run; no access |

## Gate mapping

P0 evidence is aggregated by `make check` and `make smoke`; individual mappings above point to the executing test files. P1 adds the full offline-fallback matrix, race-safe SSE, React UI tests/build, richer scenarios, and optional LinuxONE verification. No row moves to “Verified” without an executed test.
