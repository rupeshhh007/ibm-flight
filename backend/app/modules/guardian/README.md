# Enhanced Guardian monitoring agent

> **SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE**

`DeterministicGuardianAgent` is an observation-only implementation of the
frozen `GuardianAgent` protocol. It tracks bounded, current-run evidence for
each synthetic pilot, rejects replayed or out-of-order input, and emits one
critical dual-pilot incident only after both pilots meet the configured fresh,
independent evidence rule. Camera uncertainty, poor quality, or one visual
reading never establishes unresponsiveness.

The defaults in `GuardianPolicy` are deterministic demo heuristics, not medical
or aviation thresholds. Logical time comes exclusively from stored observation
events. The acknowledgement grace can therefore be evaluated only when a new
observation arrives; there is no independent timer in contract v1.

The P0 application intentionally remains wired to `MockGuardianAgent`. An
integration-owner change can select the enhanced implementation without a
contract change by replacing that constructor in `app/main.py` and rerunning
the API safety, contract, and smoke suites.

Contract-v1 limitations remain outside this module: Guardian receives no
telemetry or timer events, the API does not deliver early single-pilot
acknowledgements, and the orchestrator does not refresh a cleared incident
snapshot or invalidate Sentinel authorization after observation-driven
recovery. Until the platform owner implements and tests that propagation, a
stale approval may still refer to the orchestrator's old incident snapshot.

Accepted acknowledgements establish an event-time recovery boundary. Only
usable observations strictly newer than `acknowledged_at` count toward
recovery. If an API acknowledgement uses wall-clock time ahead of the virtual
scenario clock, recovery intentionally waits until virtual observations pass
that boundary; the platform integration should normalize or validate those
clock domains explicitly.
