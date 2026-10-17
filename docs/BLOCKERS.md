# AeroGuard Blocker and Dependency Register

This register contains only issues confirmed during repository inspection on 2026-10-17. The repository had no application/configuration files before the documentation bootstrap. A blocker is closed only after its verification step is executed and recorded.

| ID | Owner | Module | Issue | Impact | Priority | Proposed resolution | Status | Verification |
|---|---|---|---|---|---|---|---|---|
| BLK-001 | Abhinav, approval by Rupesh | Contracts | Canonical Pydantic models, enums, `interfaces.py`, mocks, fixtures, and generated contracts do not exist | Protocol signatures cannot be documented/frozen; five feature owners cannot safely implement against shared boundaries | P0 critical | Implement strict v1 contracts and conforming mocks, generate artifacts, update `CONTRACTS.md`/handoffs from source | Open | Imports, fixture validation, mock conformance, deterministic generation, and drift check pass |
| BLK-002 | Abhinav with all module owners | Platform | No FastAPI app, orchestrator, SQLite event store, API, scenario vertical slice, test suite, Makefile, frontend, or CI exists | No executable local demo; all technical P0/P1 gates are unsatisfied | P0 critical | Build the smallest authorized mock vertical slice and critical negative tests in the master execution order | Open | Backend health/state respond; scenario start/advance stores ordered events; authorization negatives and smoke pass |
| BLK-003 | Abhinav | LinuxONE | Access, target environment, s390x dependencies, and deployment configuration are absent | Remote supervisory integration cannot be implemented or claimed as verified | P1 optional | Keep local mock; request authorized access later and run the verification checklist on actual s390x | Open / non-blocking for local demo | Target reports s390x and documented build/intake/outage tests pass |

## Blocker update rules

Record reproduction/evidence in the relevant PR, name affected consumers, and link any contract request. “Code written” is not resolution; the verification column must pass. Do not add speculative risks as blockers—record them in a PR or architecture discussion until reproduced.
