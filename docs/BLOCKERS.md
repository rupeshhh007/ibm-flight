# AeroGuard Blocker and Dependency Register

This register contains only issues confirmed during repository inspection on 2026-10-17. The repository had no application/configuration files before the documentation bootstrap. A blocker is closed only after its verification step is executed and recorded.

| ID | Owner | Module | Issue | Impact | Priority | Proposed resolution | Status | Verification |
|---|---|---|---|---|---|---|---|---|
| BLK-001 | Abhinav, approval by Rupesh | Contracts | Canonical contracts and frozen interfaces were absent | Feature owners could not safely share boundaries | P0 critical | Implement strict v1 contracts/mocks, generate artifacts, and update source-based handoffs | Resolved on P0 branch; merge review pending | `make contracts-check` passed; contract/fixture/Protocol tests passed |
| BLK-002 | Abhinav with all module owners | Platform | Executable API/orchestrator/store/scenario baseline was absent | No local vertical slice or safety evidence | P0 critical | Build the minimal deterministic connected-emergency vertical slice and negatives | Resolved on P0 branch; merge review pending | `make check` and `make smoke` passed; real Uvicorn health/state probe passed |
| BLK-003 | Abhinav | LinuxONE | Access, target environment, s390x dependencies, and deployment configuration are absent | Remote supervisory integration cannot be implemented or claimed as verified | P1 optional | Keep local mock; request authorized access later and run the verification checklist on actual s390x | Open / non-blocking for local demo | Target reports s390x and documented build/intake/outage tests pass |

## Blocker update rules

Record reproduction/evidence in the relevant PR, name affected consumers, and link any contract request. “Code written” is not resolution; the verification column must pass. Do not add speculative risks as blockers—record them in a PR or architecture discussion until reproduced.
