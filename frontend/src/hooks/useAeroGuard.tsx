// Single source of client-side state for all three screens.
//
// How data flows:
//   1. Every POLL_MS we fetch GET /state, GET /incidents and any events after the
//      highest seq we already hold (REST polling; the SSE endpoint is P1 and not
//      registered by the backend yet).
//   2. Commands (start/advance/ack/ATC/...) go through `runCommand`, which allows
//      only one in-flight command, applies the backend's returned snapshot and
//      events, and records an honest outcome (accepted / duplicate / rejected).
//   3. The UI never shows success before the backend's CommandResponse confirms it.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api as defaultApi, ApiError, newCommandId, type Api } from "../api/client";
import { latestSeq, mergeEvents } from "../api/events";
import type {
  ATCDecisionType,
  CommandResponse,
  GuardianIncident,
  PilotId,
  ScenarioMetadata,
  SimulatorActionType,
  StoredEvent,
  SystemSnapshot,
} from "../api/types";

export const POLL_MS = 1500;

export type Connection = "connecting" | "online" | "offline";

export interface CommandOutcome {
  label: string;
  status: "accepted" | "duplicate" | "rejected" | "network";
  message: string;
  code?: string;
  details?: string[];
  at: number;
  /** Present for network failures: resends the SAME body (same command_id), so a retry is idempotent. */
  retry?: () => void;
}

export interface AeroGuardCommands {
  start: (scenarioId: string) => void;
  advance: (deltaMs: number) => void;
  reset: () => void;
  acknowledge: (pilotId: PilotId) => void;
  atcDecision: (decision: ATCDecisionType, action: SimulatorActionType, operatorId: string) => void;
  setLink: (connected: boolean) => void;
}

export interface AeroGuardState {
  snapshot: SystemSnapshot | null;
  scenarios: ScenarioMetadata[] | null;
  incidents: GuardianIncident[];
  events: StoredEvent[];
  connection: Connection;
  lastSyncAt: number | null;
  syncError: string | null;
  pending: string | null;
  outcome: CommandOutcome | null;
  dismissOutcome: () => void;
  commands: AeroGuardCommands;
  refresh: () => Promise<void>;
}

const AeroGuardContext = createContext<AeroGuardState | null>(null);

/** Domain timestamps follow the backend's virtual clock, not the browser's wall clock. */
function domainNow(snapshot: SystemSnapshot | null): string {
  return snapshot?.virtual_time ?? new Date().toISOString();
}

/**
 * A snapshot is applied only if it is at least as new as the one we hold.
 * This stops a slow poll that started before a command from overwriting the
 * fresher snapshot that command returned.
 */
export function isNewerSnapshot(current: SystemSnapshot | null, next: SystemSnapshot): boolean {
  return current === null || next.latest_event_seq >= current.latest_event_seq;
}

interface ProviderProps {
  children: ReactNode;
  client?: Api;
  pollMs?: number;
}

export function AeroGuardProvider({ children, client = defaultApi, pollMs = POLL_MS }: ProviderProps) {
  const [snapshot, setSnapshot] = useState<SystemSnapshot | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioMetadata[] | null>(null);
  const [incidents, setIncidents] = useState<GuardianIncident[]>([]);
  const [events, setEvents] = useState<StoredEvent[]>([]);
  const [connection, setConnection] = useState<Connection>("connecting");
  const [lastSyncAt, setLastSyncAt] = useState<number | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<CommandOutcome | null>(null);

  // Refs give command builders and the poll loop the latest values without
  // re-creating callbacks (avoids stale closures carrying an old run ID).
  const snapshotRef = useRef<SystemSnapshot | null>(null);
  const eventsRef = useRef<StoredEvent[]>([]);
  const pendingRef = useRef<string | null>(null);
  // Bumped whenever a command starts or finishes, so a poll can tell whether a
  // command overlapped it (and its snapshot might therefore be outdated).
  const commandEpochRef = useRef(0);

  const applySnapshot = useCallback((next: SystemSnapshot, authoritative = false) => {
    if (!authoritative && !isNewerSnapshot(snapshotRef.current, next)) return;
    snapshotRef.current = next;
    setSnapshot(next);
  }, []);

  const applyEvents = useCallback((incoming: StoredEvent[]) => {
    const merged = mergeEvents(eventsRef.current, incoming);
    if (merged !== eventsRef.current) {
      eventsRef.current = merged;
      setEvents(merged);
    }
  }, []);

  const refresh = useCallback(async () => {
    const epochAtStart = commandEpochRef.current;
    try {
      const [state, incidentList] = await Promise.all([client.state(), client.incidents()]);
      // With no command overlapping this poll, GET /state is the backend's current
      // truth even if its seq went DOWN (backend restarted on a fresh database).
      const authoritative = epochAtStart === commandEpochRef.current && pendingRef.current === null;
      if (authoritative && state.latest_event_seq < latestSeq(eventsRef.current)) {
        eventsRef.current = []; // a different event store: drop history we can no longer match
        setEvents([]);
      }
      applySnapshot(state, authoritative);
      setIncidents(incidentList.incidents);
      // Catch up on history page by page until we reach the backend's latest seq.
      for (let page = 0; page < 20; page += 1) {
        const history = await client.events(latestSeq(eventsRef.current));
        applyEvents(history.events);
        if (history.events.length < history.limit || latestSeq(eventsRef.current) >= history.latest_event_seq) break;
      }
      setConnection("online");
      setSyncError(null);
      setLastSyncAt(Date.now());
    } catch (error) {
      const apiError = error instanceof ApiError ? error : null;
      setConnection(apiError?.isNetworkError ? "offline" : "online");
      setSyncError(apiError?.message ?? "Unexpected error while syncing with the backend");
    }
  }, [client, applySnapshot, applyEvents]);

  // Scenario catalogue: load once, retry on the poll cadence until it succeeds.
  useEffect(() => {
    if (scenarios !== null) return;
    let cancelled = false;
    const load = () =>
      client
        .scenarios()
        .then((list) => !cancelled && setScenarios(list.scenarios))
        .catch(() => undefined);
    load();
    const timer = setInterval(load, pollMs * 2);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [client, pollMs, scenarios]);

  // Polling loop. setTimeout chaining (not setInterval) prevents overlapping polls.
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      await refresh();
      if (!cancelled) timer = setTimeout(tick, pollMs);
    };
    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [refresh, pollMs]);

  const runCommand = useCallback(
    async (label: string, send: () => Promise<CommandResponse>) => {
      if (pendingRef.current) return; // one command at a time: no accidental double submits
      pendingRef.current = label;
      commandEpochRef.current += 1;
      setPending(label);
      try {
        const response = await send();
        // A duplicate replay returns the snapshot recorded the FIRST time, which may
        // be stale now — so we only trust fresh responses' snapshots, then re-sync.
        if (!response.duplicate) applySnapshot(response.snapshot);
        applyEvents(response.events);
        setOutcome({
          label,
          status: response.duplicate ? "duplicate" : "accepted",
          message: response.message,
          at: Date.now(),
        });
      } catch (error) {
        const apiError =
          error instanceof ApiError ? error : new ApiError("CLIENT_ERROR", String(error), 0);
        setOutcome({
          label,
          status: apiError.isNetworkError ? "network" : "rejected",
          message: apiError.message,
          code: apiError.code,
          details: apiError.details,
          at: Date.now(),
          retry: apiError.isNetworkError ? () => void runCommand(label, send) : undefined,
        });
      } finally {
        pendingRef.current = null;
        commandEpochRef.current += 1;
        setPending(null);
        void refresh();
      }
    },
    [applySnapshot, applyEvents, refresh],
  );

  const commands = useMemo<AeroGuardCommands>(() => {
    // Commands that act on the active run read its ID at click time from the ref.
    const activeRun = (label: string): string | null => {
      const runId = snapshotRef.current?.scenario_run_id ?? null;
      if (!runId) {
        setOutcome({ label, status: "rejected", code: "NO_ACTIVE_SCENARIO", message: "Start a scenario first.", at: Date.now() });
      }
      return runId;
    };

    return {
      start: (scenarioId) => {
        const body = { command_id: newCommandId(), scenario_id: scenarioId };
        void runCommand(`Start ${scenarioId}`, () => client.startScenario(body));
      },
      advance: (deltaMs) => {
        const runId = activeRun("Advance");
        if (!runId) return;
        const body = { command_id: newCommandId(), scenario_run_id: runId, delta_ms: deltaMs };
        void runCommand(`Advance ${deltaMs} ms`, () => client.advanceScenario(body));
      },
      reset: () => {
        const runId = activeRun("Reset");
        if (!runId) return;
        const body = { command_id: newCommandId(), scenario_run_id: runId };
        void runCommand("Reset scenario", () => client.resetScenario(body));
      },
      acknowledge: (pilotId) => {
        const runId = activeRun("Acknowledge");
        const incident = snapshotRef.current?.active_incident;
        if (!runId) return;
        if (!incident) {
          setOutcome({ label: "Acknowledge", status: "rejected", code: "NO_ACTIVE_INCIDENT", message: "There is no active alert to acknowledge.", at: Date.now() });
          return;
        }
        const body = {
          command_id: newCommandId(),
          scenario_run_id: runId,
          pilot_id: pilotId,
          alert_id: incident.incident_id, // backend matches alert_id to the active incident
          acknowledged_at: domainNow(snapshotRef.current),
        };
        void runCommand(`Acknowledge ${pilotId}`, () => client.acknowledge(body));
      },
      atcDecision: (decision, action, operatorId) => {
        const runId = activeRun("ATC decision");
        const incident = snapshotRef.current?.active_incident;
        if (!runId) return;
        if (!incident) {
          setOutcome({ label: "ATC decision", status: "rejected", code: "NO_ACTIVE_INCIDENT", message: "No active incident is awaiting a decision.", at: Date.now() });
          return;
        }
        const body = {
          command_id: newCommandId(),
          scenario_run_id: runId,
          incident_id: incident.incident_id,
          decision,
          requested_action: action,
          operator_id: operatorId,
          issued_at: domainNow(snapshotRef.current),
        };
        void runCommand(`ATC ${decision}`, () => client.atcDecision(body));
      },
      setLink: (connected) => {
        const runId = activeRun("ATC link");
        if (!runId) return;
        const body = {
          command_id: newCommandId(),
          scenario_run_id: runId,
          atc_link_connected: connected,
          changed_at: domainNow(snapshotRef.current),
        };
        void runCommand(connected ? "Connect simulated ATC" : "Disconnect simulated ATC", () => client.setLink(body));
      },
    };
  }, [client, runCommand]);

  const value: AeroGuardState = {
    snapshot,
    scenarios,
    incidents,
    events,
    connection,
    lastSyncAt,
    syncError,
    pending,
    outcome,
    dismissOutcome: () => setOutcome(null),
    commands,
    refresh,
  };

  return <AeroGuardContext.Provider value={value}>{children}</AeroGuardContext.Provider>;
}

export function useAeroGuard(): AeroGuardState {
  const value = useContext(AeroGuardContext);
  if (!value) throw new Error("useAeroGuard must be used inside <AeroGuardProvider>");
  return value;
}
