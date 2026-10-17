# AeroGuard Pull Request

> **SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE**

## Description

What behavior changes, and why?

## Scope and ownership

- Developer / owner:
- Feature branch:
- Verified baseline SHA:
- Owned paths changed:
- Cross-owner approvals (if any):

## Files modified

List source, tests, documentation, dependency, and generated files separately.

## Contract impact

- [ ] No public contract impact
- [ ] Approved contract change request linked
- [ ] Canonical source changed only by Abhinav after Rupesh approval
- [ ] Generated artifacts regenerated, not hand-edited
- [ ] Downstream owners/consumers identified

Describe models, events, enums, routes, Protocols, scenarios, or persistence formats affected:

## Tests executed

| Exact command | Result | Relevant output/link |
|---|---|---|
| | | |

Do not mark an unexecuted check as passed.

## Compatibility checks

- [ ] Owned unit/negative tests pass
- [ ] Contract drift check passes without mutating the tree
- [ ] Cross-module/integration tests pass
- [ ] Mock smoke path passes
- [ ] Frontend typecheck/build passes if applicable
- [ ] Mock/no-webcam/no-IBM mode remains functional
- [ ] Old-run and duplicate-command behavior remains safe

## Security and simulation safety

- [ ] No secrets or credentials committed
- [ ] No live aircraft/avionics/operational ATC/navigation integration
- [ ] Guardian does not control the simulator
- [ ] Sentinel authorization and independent simulator validation are preserved
- [ ] Camera uncertainty is not presented as diagnosis
- [ ] ATC disconnection alone cannot trigger fallback
- [ ] No LLM-generated simulator action approval

## Documentation updates

List updated docs and any implementation-status changes.

## Screenshots

Required for visible UI changes; otherwise write “Not applicable.”

## Known limitations and blockers

List unresolved behavior, omitted checks, platform gaps, and follow-up owner.

## Reviewer checklist

- [ ] Changed paths comply with `docs/OWNERSHIP.md`
- [ ] Architecture/contracts match approved source of truth
- [ ] Negative and regression tests cover the change
- [ ] Test claims include exact evidence
- [ ] Generated files match generators
- [ ] Error, retry, reset, and stale/duplicate paths are safe
- [ ] Documentation distinguishes implemented from planned
