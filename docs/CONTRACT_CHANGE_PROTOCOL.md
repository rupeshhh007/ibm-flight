# Contract Change Protocol

## Purpose

After v1 freeze, public models, enums, events, routes, Protocols, persistence formats, scenario IDs, and generated artifacts cannot change informally. Rupesh approves architecture changes; Abhinav assesses consumers and is the sole canonical-contract editor.

## Required workflow

1. **Detect and reproduce.** The feature owner demonstrates why the current contract prevents a required behavior. Prefer a failing test or concrete payload/signature example.
2. **Write a minimal request.** In the PR description or `docs/BLOCKERS.md`, identify the current contract, exact proposed change, reason, affected owners/consumers, compatibility risk, and possible in-module adapter shim.
3. **Architecture decision.** Rupesh approves, rejects, or requests a smaller change. No source or generated artifact changes before approval.
4. **Consumer assessment.** Abhinav enumerates backend modules, API clients, fixtures, database formats, frontend generated types, docs, and deployment consumers.
5. **Canonical edit.** Abhinav modifies only authoritative Pydantic models/Protocol definitions/API declarations. If a safe local adapter can preserve v1, prefer it.
6. **Regenerate.** Abhinav runs the canonical generator for OpenAPI, JSON Schema, and TypeScript. Nobody hand-edits generated files.
7. **Regression coverage.** Add positive, negative, fixture, backward-compatibility, old-run/deduplication, and downstream integration tests appropriate to the change.
8. **Verify compatibility.** Run contract drift, backend tests, frontend typecheck/build, smoke test, and affected owner suites. Record exact results.
9. **Merge contract first.** Prefer a small contract PR before dependent feature PRs. An atomic cross-module PR requires explicit approval from every affected owner.
10. **Update consumers.** Each module owner rebases onto the contract commit, updates only owned code/tests, and proves compatibility before merge.

## Change request template

```text
Contract change ID:
Requester / owner:
Current model, enum, route, Protocol, or format:
Reproduction / failing test:
Minimal proposed change:
Why an adapter cannot preserve v1:
Affected consumers and owners:
Compatibility / migration risk:
Required generated artifacts:
Required tests:
Rupesh decision:
Abhinav impact assessment:
```

## Prohibited shortcuts

Do not add local JSON fields, widen to catch-all dictionaries, change enum literals, create alternate interfaces/routes/databases, edit generated types, or silently change a persisted shape. Urgency does not bypass the process; record the blocker and seek the smallest safe change.
