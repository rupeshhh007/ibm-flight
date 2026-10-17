# AeroGuard Test Matrix

## Status

No application source or executable test suite exists. Every row is currently **Not implemented / not run**. P0 and P1 gates remain open. IDs are stable traceability labels for the implementation PRs.

| ID | Module | Objective | Test input | Expected result | Priority | Type | Status |
|---|---|---|---|---|---|---|---|
| CON-001 | Contracts | Validate representative canonical models | Valid fixture per model | Strict parse and normalized UTC output | P0 | Contract | Not implemented |
| CON-002 | Events | Reject event/payload mismatch | `TELEMETRY_UPDATED` with observation payload | Validation failure using common error semantics | P0 | Negative contract | Not implemented |
| CON-003 | Contracts | Reject invalid UUID, naive time, enum, and bounds | Malformed fields and quality outside `0..1` | Deterministic validation errors | P0 | Negative contract | Not implemented |
| VIS-001 | Vision | Camera obstruction remains uncertain | unavailable camera/hidden face | `UNKNOWN`; no incapacity assertion | P0 | Unit/safety | Not implemented |
| VIS-002 | Vision | Validate bounded observation quality/duration | Boundary and out-of-range values | Boundaries accepted; invalid values rejected | P0 | Unit | Not implemented |
| GUA-001 | Guardian | Normal observations keep normal state | Responsive observations and nominal telemetry | `NORMAL`; no incident | P0 | Unit | Not implemented |
| GUA-002 | Guardian | Single concern requests acknowledgement only | One pilot possibly unresponsive | Suspicion/ack flow; no dual claim/action | P0 | Unit/safety | Not implemented |
| GUA-003 | Guardian | Responsive peer blocks dual-incapacity action | Concern for pilot 1; responsive pilot 2 | No dual escalation that can authorize action | P0 | Negative safety | Not implemented |
| GUA-004 | Guardian | Evidence/rule is auditable | Repeated qualifying evidence and missed ack | Incident contains current-run IDs and exact rule | P0 | Unit | Not implemented |
| GUA-005 | Guardian | Recovery is explicit | Valid ack/responsive evidence | `RECOVERING` then documented `NORMAL` transition | P0 | Unit | Not implemented |
| SEN-001 | Sentinel | Connected path waits for approval | Active escalation; link connected | `AWAITING_ATC`; no simulator action | P0 | Negative safety | Not implemented |
| SEN-002 | Sentinel | Reject decision cannot authorize | Matching `REJECT` | Audited rejection; no action | P0 | Negative safety | Not implemented |
| SEN-003 | Sentinel | Reject mismatched/stale approval | Wrong incident or old run | Audited rejection; no action | P0 | Negative safety | Not implemented |
| SEN-004 | Sentinel | Duplicate approval is idempotent | Repeat same `command_id` | Original response/no second action | P0 | Negative safety | Not implemented |
| SEN-005 | Sentinel | Disconnect toggle alone cannot act | Link changed to disconnected only | No fallback and no action | P0 | Negative safety | Not implemented |
| SEN-006 | Sentinel | Fallback requires every prerequisite | Omit each stronger-evidence prerequisite in turn | No action; reason identifies failed gate | P0 | Negative safety | Not implemented |
| SEN-007 | Sentinel | Valid fallback is restricted | All current-run prerequisites | Exactly one permitted scripted symbolic action | P0 | Integration | Not implemented |
| SIM-001 | Simulator | Reject unauthorized enum/action | Unknown or disallowed input | Predictable rejection; no state change | P0 | Negative unit | Not implemented |
| SIM-002 | Simulator | Validate run and transition independently | Old run or invalid transition | Rejection even if caller requested action | P0 | Negative unit | Not implemented |
| CLK-001 | Clock | Advance deterministically without sleep | Bounded `delta_ms` values | Exact inclusive virtual-time boundary processing | P0 | Unit | Not implemented |
| SCN-001 | Scenarios | Stable catalogue | List scenarios | Exactly five frozen IDs | P0 | Contract | Not implemented |
| SCN-002 | Scenarios | Deterministic replay | Same scenario/advance sequence twice | Equivalent domain outcomes aside from generated IDs | P0 | Scenario | Not implemented |
| SCN-003 | Reset | Isolate old run without deleting audit | Reset then issue old-run command | New run unchanged; old history queryable | P0 | Integration/safety | Not implemented |
| API-001 | API | Health and state are typed | GET health/readiness/state | Documented statuses and valid response models | P0 | API | Not implemented |
| API-002 | API | Invalid body uses common error | Bad enum/UUID/time | Stable `CommonApiError`; no mutation | P0 | Negative API | Not implemented |
| API-003 | API | Pagination is bounded | Negative/zero/excessive `limit` | Deterministic reject or documented clamp | P0 | Negative API | Not implemented |
| STO-001 | Event store | Sequence is ordered and persistent | Append batch, restart/read after seq | Unique strictly increasing sequence; no skip | P0 | Persistence | Not implemented |
| STO-002 | Event store | Event and command IDs deduplicate | Duplicate identifiers | No duplicate commit/effect | P0 | Negative persistence | Not implemented |
| SSE-001 | SSE | Replay/live handoff has no gap | Commit during subscriber join | Every committed seq delivered once after client dedup | P1 | Concurrency integration | Not implemented |
| SSE-002 | SSE | Reconnect and ordering | `Last-Event-ID`, duplicate/out-of-order delivery | Client applies only new increasing seq | P1 | Integration | Not implemented |
| SSE-003 | SSE | Bound queue and cleanup | Slow/disconnected subscriber | Bounded resource use and clean disconnect | P1 | Reliability | Not implemented |
| FE-001 | Frontend | Generated API compatibility | Production typecheck/build | No handwritten duplicate response models or TS errors | P1 | Frontend | Not implemented |
| FE-002 | Frontend | Errors/loading/status are visible | API failure and empty state | Safe status banner; controls do not fake success | P1 | Frontend | Not implemented |
| GEN-001 | Codegen | Detect generated drift | Modify canonical source without regeneration | `make contracts-check` exits nonzero without mutation | P0 | Build/contract | Not implemented |
| E2E-001 | Full mock | Normal flight end to end | Start/advance `normal_flight` | Stored ordered events; no incident/action | P0 | End-to-end | Not implemented |
| E2E-002 | Full mock | Connected approval gate | Connected dual scenario, approve once | Nothing before approval; one allowed action after | P0 | End-to-end | Not implemented |
| E2E-003 | Full mock | Camera obstruction safety | `camera_obstructed` | `UNKNOWN`; no action from obstruction | P0 | End-to-end | Not implemented |
| IBM-001 | Remote sync | Local operation survives remote failure | Mock timeout/disconnect/backlog | Local path continues; pending count/audit updates | P1 | Integration | Not implemented |
| IBM-002 | LinuxONE | Verify actual target compatibility | s390x environment, dependency install, intake probe | Evidence-backed result; no x86-only claim | P1/optional | Deployment | Not run; no access |

## Gate mapping

P0 requires at least `CON-001..003`, critical Vision/Guardian/Sentinel/Simulator negatives, `CLK-001`, `SCN-001..003`, `API-001..003`, `STO-001..002`, `GEN-001`, and mock end-to-end coverage. P1 adds race-safe SSE, frontend build/client tests, expanded five-scenario coverage, and optional LinuxONE verification. No row may move to “Verified” without recording the exact command and result in its implementing PR or this file.
