# AeroGuard Integration Guide

## Current readiness

The documentation foundation exists, but the executable P0 foundation does not. Do not create implementation branches from this documentation-only state and call them contract-compatible. Abhinav must first implement canonical source/contracts, mocks, API, event store, generation, and P0 tests; Rupesh must approve the architecture baseline; the team must record the same verified `main` commit SHA.

## Foundation and branch creation

1. Complete every P0 launch-gate item in the master specification.
2. Run and record exact results for `make contracts-check`, backend tests, critical negative tests, and `make smoke`.
3. Obtain Rupesh's architecture approval and Abhinav's integration sign-off.
4. Create a local foundation commit only when authorized. Do not publish a remote or create one without authorization.
5. Share the verified full SHA in team chat and record it in the integration checkpoint log.
6. Every developer checks out that same commit, then creates only their assigned branch: `feat/vision`, `feat/simulator`, `feat/guardian`, `feat/sentinel`, `feat/frontend`, or `feat/platform`.
7. Before editing, read `AGENTS.md`, architecture, contracts, ownership, this guide, and the matching handoff prompt; inspect actual source Protocols and generated schema.

## Parallel development rules

Developers commit only owned files and tests. Open small PRs when meaningful tests pass. Mocks remain usable so modules can test against stable peers. Public-contract gaps are raised immediately through [Contract Change Protocol](CONTRACT_CHANGE_PROTOCOL.md); they do not become private JSON variants.

Coding can proceed concurrently. Practical integration priority is:

1. Rohan's simulator and Rupesh's Guardian.
2. Amrit's Sentinel.
3. Tarun's real frontend.
4. Tejas's optional camera adapter.
5. IBM remote integration.

This is an integration priority, not a rule that blocks an independently testable PR.

## Pull-request workflow

1. Rebase/merge the latest verified baseline according to team policy; never rewrite shared history.
2. Confirm every changed path has a single authorized owner.
3. Describe behavior, contract impact, files, tests, results, limitations, and downstream consumers.
4. Run the module suite plus `make contracts-check` and `make smoke` when available.
5. For UI work, include screenshots and frontend typecheck/build results.
6. Abhinav checks ownership, generated drift, API compatibility, cross-module regression, and smoke behavior.
7. The feature owner reviews domain behavior; Rupesh reviews architectural/state-machine changes.
8. Merge only with required checks green or a fully recorded manual checklist if branch protection is unavailable.

Never push directly to `main`, force-push shared refs, merge with unexplained failures, or claim a check that was not run.

## Shared dependencies and files

Backend dependencies are coordinated by Abhinav; frontend dependencies by Tarun. Requests state need, pinned version, optionality, licensing/platform implications, and s390x impact. Generated artifacts are regenerated only by Abhinav. Shared entry-point edits should be isolated and owner-reviewed to minimize conflicts.

## Automated and manual gates

Target CI runs reproducible dependency installation, backend unit/contract/scenario/integration tests, contract drift comparison, static/lint checks if configured, frontend typecheck/build, and mock smoke tests. GitHub Actions on Linux x86 does not verify LinuxONE s390x compatibility.

If branch protection cannot be configured, reviewers manually confirm:

- ownership compliance;
- no unapproved contract or generated edits;
- all reported commands and outputs;
- safety-negative coverage;
- no committed secrets or operational-aviation claims;
- mock/no-webcam/no-IBM path still works;
- documentation reflects implemented behavior.

## Checkpoint cadence

Use short team syncs after foundation, then approximately 4, 8, 12, 17, and 21 hours after hackathon start. Do not convert these relative checkpoints into invented clock times.

| Checkpoint | Required report |
|---|---|
| Foundation | Baseline SHA, exact gate results, open blockers, contract freeze status |
| ~4 hours | First module tests, dependency/contract blockers, API/schema drift |
| ~8 hours | Simulator/Guardian integration status and critical negatives |
| ~12 hours | Sentinel authorization paths and first end-to-end path |
| ~17 hours | Frontend/demo integration, all five scenarios, SSE/P1 status |
| ~21 hours | Known-good demo commit, final defects, presentation readiness |

As soon as one full scenario works, retain a stable known-good tagged demo commit according to team authorization. In the final three hours, prefer defect fixes, tests, rehearsal, and presentation over features.

## Conflict and blocker handling

For a path conflict, stop and involve its owner. For a contract conflict, write a minimal change request and merge the approved contract before consumers. For an integration failure, preserve the last known-good revision, isolate the first failing commit, and add a regression test. Keep [Blockers](BLOCKERS.md) current with reproduction, impact, proposed resolution, owner, and verification; only retesting can close a blocker.

## Recovery procedures

- Do not use destructive reset or history rewriting on shared work.
- Create a repair branch from the last verified baseline or known-good demo commit.
- Revert through a normal reviewed commit when necessary and authorized.
- Restore generated files by rerunning the generator, not manual editing.
- If remote sync or optional CV breaks, disable that adapter and keep deterministic mocks active.
- If SSE is unstable, retain REST event history/polling and mark SSE as P1 rather than weakening ordering guarantees.

## Feature freeze and acceptance

P0 and P1 definitions in the master specification are authoritative. During final stabilization, a change is accepted only if it preserves the safety invariants, has owner review, includes regression evidence, keeps smoke/check green, and improves the known-good demo. Documentation completion alone never satisfies the technical gates.
