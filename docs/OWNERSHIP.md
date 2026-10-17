# AeroGuard Ownership

## Governance

Rupesh is the architecture decision approver. Abhinav is integration lead and, after contract freeze, the only editor of canonical contracts following Rupesh's approval. Ownership is not permission to rewrite another developer's implementation. Cross-owner changes require the owning developer's review.

## Primary assignments

| Developer | Responsibility | Branch | Primary owned path |
|---|---|---|---|
| Tejas | Computer Vision & Pilot Monitoring | `feat/vision` | `backend/app/modules/vision/` |
| Rohan | Aircraft Telemetry & Flight Simulation | `feat/simulator` | `backend/app/modules/simulator/`, `backend/app/scenarios/` |
| Rupesh | Guardian Monitoring Agent | `feat/guardian` | `backend/app/modules/guardian/` |
| Amrit | Sentinel Emergency Response Agent | `feat/sentinel` | `backend/app/modules/sentinel/` |
| Tarun | Frontend, Cockpit & ATC UI | `feat/frontend` | `frontend/src/` except `frontend/src/api/generated/` |
| Abhinav | Backend Integration, IBM LinuxONE & Testing | `feat/platform` | `backend/app/core/`, `backend/app/api/`, contracts, deployment, CI |

## Writable path ownership

| Path or file | Single owner | Review/coordination rule |
|---|---|---|
| `backend/app/modules/vision/**` | Tejas | Public boundary change requires contract process |
| `backend/tests/unit/vision/**` | Tejas | Abhinav may add integration coverage elsewhere |
| `backend/app/modules/simulator/**` | Rohan | Simulator authorization invariants reviewed by Amrit/Abhinav |
| `backend/app/scenarios/**` | Rohan | Stable IDs cannot change without contract process |
| `backend/tests/unit/simulator/**`, `backend/tests/scenarios/**` | Rohan | Abhinav reviews shared integration implications |
| `backend/app/modules/guardian/**` | Rupesh | Architecture changes documented in `DECISIONS.md` |
| `backend/tests/unit/guardian/**` | Rupesh | Safety negatives required |
| `backend/app/modules/sentinel/**` | Amrit | Simulator/API changes require owner reviews |
| `backend/tests/unit/sentinel/**` | Amrit | Safety negatives required |
| `backend/app/modules/audit/**` | Abhinav | Coordinate if feature-specific behavior is added |
| `frontend/src/**` excluding generated | Tarun | Shared entry-point changes stay small and reviewed |
| `frontend/package.json`, `frontend/package-lock.json` | Tarun | Feature owners request frontend dependency changes through Tarun |
| `frontend/src/api/generated/**` | Abhinav | Generated only; never hand edit |
| `backend/app/contracts/**` | Abhinav | Rupesh approval required after freeze |
| `backend/app/core/**`, `backend/app/api/**`, `backend/app/main.py`, `backend/app/config.py` | Abhinav | Preserve module interfaces and ownership boundaries |
| `backend/pyproject.toml` and backend lock/config files | Abhinav | Feature owners request dependency additions |
| `backend/tests/contracts/**`, `backend/tests/integration/**` | Abhinav | Module owners contribute cases through review |
| `contracts/fixtures/**` | Abhinav | Fixture meaning reviewed by relevant feature owner |
| `contracts/generated/**` | Abhinav | Generated only |
| `scripts/**`, `Makefile`, `.env.example`, `.gitignore` | Abhinav | Integration-owned shared files |
| `.github/workflows/**`, `.github/pull_request_template.md` | Abhinav | CI changes reviewed by affected owners |
| Deployment/container/LinuxONE files | Abhinav | No remote changes without authorization |
| `README.md`, `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` | Rupesh | Abhinav reviews implementation claims and commands |
| `docs/CONTRACTS.md`, `docs/CONTRACT_CHANGE_PROTOCOL.md`, `docs/INTEGRATION.md`, `docs/TEST_MATRIX.md`, `docs/IBM_LINUXONE.md`, `docs/BLOCKERS.md` | Abhinav | Rupesh approves architecture/contract changes |
| `docs/OWNERSHIP.md`, `docs/TEAM_HANDOFF.md`, `docs/DEMO_RUNBOOK.md` | Abhinav | All affected owners review their sections |
| `AEROGUARD_CODEX_MASTER_BOOTSTRAP_V3.md` | Rupesh | Normative source; change only by explicit team decision |

No independent agent may modify generated output. A generator change and regenerated output are one Abhinav-owned change.

## Testing responsibility

Every developer owns deterministic unit and negative tests for their module. Abhinav owns contract, integration, API, persistence, drift, and end-to-end suites and coordinates cross-module regressions. Tarun owns frontend component/client tests and build/typecheck. Optional real-CV tests must be segregated so default CI remains webcam-free.

## Dependency management

Backend dependency requests go to Abhinav; frontend dependency requests go to Tarun. The request must state purpose, version, platform impact, s390x implications where relevant, and whether it is optional. No feature branch unilaterally adds a shared dependency.

## Review and conflict resolution

1. Abhinav checks changed paths against this table.
2. The path owner reviews behavior in their domain.
3. Rupesh resolves architecture conflicts and approves contract-breaking decisions.
4. Abhinav assesses consumers, integration order, tests, and generated drift.
5. If no safe decision is ready, record the issue in `docs/BLOCKERS.md`; do not merge a private workaround into public shapes.
