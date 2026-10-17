# IBM LinuxONE Integration

## Status

LinuxONE integration is optional, conceptual, and unverified. The repository contains no remote-sync adapter, deployment manifest, credentials, endpoint, s390x build evidence, or live service. This document must not be read as a deployment claim.

## Project-specific purpose

A LinuxONE environment may host the portable supervisory portion of AeroGuard: receive copies of committed simulation events, retain/audit them, and support non-critical analytics or demo observability. It must not process webcam frames, authorize local simulator actions, or sit in the local Guardian-to-Sentinel critical path.

```text
Local deterministic simulation
  -> committed StoredEvents
  -> optional RemoteSyncAdapter with bounded retry/backlog
  -> authenticated LinuxONE supervisory event intake
  -> audit storage / non-critical analytics

Remote unavailable
  -> local simulation continues
  -> pending_sync_count reflects backlog
  -> no change to simulated ATC authorization
```

## Supervisory responsibilities

- Accept validated, versioned event copies through a documented authenticated transport.
- Deduplicate by stable event identity and retain original local sequence/run metadata.
- Provide audit and analytics without rewriting local truth.
- Report remote-sync connectivity and backlog separately from simulated ATC-link state.
- Reject unsupported schema versions and malformed inputs safely.

It may not issue operational commands, replace the local event store, or make local response contingent on network availability.

## Linux s390x compatibility

The deployment target is Linux `s390x`. GitHub Actions on x86 does not prove compatibility. Before choosing dependencies or images:

1. Confirm Python 3.11 and every required package has an s390x wheel or can be built from source in the target environment.
2. Use multi-architecture/base images that explicitly publish s390x manifests; do not assume x86 or Apple Silicon images work.
3. Exclude optional OpenCV/MediaPipe and webcam code from the supervisory dependency set.
4. Avoid native extensions unless target build/install is demonstrated.
5. Record OS, architecture, Python version, package lock, image digest, and exact verification commands.

## Configuration and security

Exact environment variable names await implementation. Configuration will need an explicit enable flag, remote URL, authentication reference, timeouts, bounded retry/backlog settings, and TLS verification. Secrets belong in the deployment environment/secret store, never Git or example values. The intake must validate size, schema version, event identity, and authorization. Do not invent a production identity model or expose the local demo API publicly.

## Failure isolation and mock mode

The default `RemoteSyncAdapter` is a local mock. When remote sync is disabled or failing, committed events remain in local SQLite, local REST/SSE continue, Sentinel authorization is unchanged, and the snapshot reports separate remote status/pending count. Retries must not duplicate remote records or exhaust unbounded memory/disk. No remote acknowledgement can stand in for simulated ATC approval.

## Deployment prerequisites

- Explicit authorization and verified LinuxONE access.
- An s390x-compatible dependency/container build.
- Agreed ingress, TLS, authentication, secret handling, storage, and retention.
- A non-production simulation namespace and clear safety labels.
- Health/readiness and log/metric collection.
- Rollback procedure and local isolation test.

No port, hostname, service name, account, credential, or deployment command is documented until it exists and is verified.

## Verification requirements

A real integration claim requires evidence for:

- architecture detection reports `s390x`;
- clean dependency installation/build on target;
- process health/readiness;
- authenticated valid event ingestion and malformed-event rejection;
- duplicate-event idempotency;
- reconnect/backlog drain without local interruption;
- remote outage while the local mock scenario completes safely;
- no CV/native desktop dependency in the supervisory artifact;
- exact command output, date, and target environment recorded.

Until all applicable evidence exists, present LinuxONE as an optional architecture boundary, not a deployed achievement.
