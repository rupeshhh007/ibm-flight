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
import { mergeEvents } from "../api/events";
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
  status: "accepted" | "duplicate" | "rejected" | "network" | "uncertain";
  message: string;
  code?: string;
  details?: string[];
  at: number;
  /** Present for network or uncertain transport failures: resends the SAME body (same command_id), so a retry is idempotent. */
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
  // Dedicated history pagination cursor tracking the sequential history seq fetched
  // from client.events. Never advanced by command responses or out-of-order events.
  const historyCursorRef = useRef<number>(0);
  const pendingRef = useRef<string | null>(null);
  // Bumped whenever a command starts or finishes, so a poll can tell whether a
  // command overlapped it (and its snapshot might therefore be outdated).
  const commandEpochRef = useRef(0);
  // Monotonically increasing identifier for active command executions to prevent late
  // responses from timed-out or cancelled requests from overwriting state or clearing locks.
  const commandGenerationRef = useRef(0);
  // Request sequence generator for refresh calls to reject superseded responses.
  const refreshSeqRef = useRef(0);
  const lastAppliedRefreshSeqRef = useRef(0);

  const applySnapshot = useCallback((next: SystemSnapshot, authoritative = false): boolean => {
    const current = snapshotRef.current;
    if (!authoritative) {
      if (!isNewerSnapshot(current, next)) return false;
    } else {
      // Authoritative GET /state: accept if seq went down (fresh backend/db reset) or is newer.
      // But if it's within the SAME active scenario run and the sequence is strictly older, reject it.
      if (
        current &&
        current.scenario_run_id !== null &&
        current.scenario_run_id === next.scenario_run_id &&
        next.latest_event_seq < current.latest_event_seq
      ) {
        return false;
      }
    }
    snapshotRef.current = next;
    setSnapshot(next);
    return true;
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
    const reqSeq = ++refreshSeqRef.current;
    try {
      const [state, incidentList] = await Promise.all([client.state(), client.incidents()]);

      // If a newer refresh request has already been applied, this response is superseded.
      if (reqSeq < lastAppliedRefreshSeqRef.current) {
        return;
      }

      // Check if any command overlapped this poll.
      const noCommandOverlap = epochAtStart === commandEpochRef.current && pendingRef.current === null;

      // Prevent a response for a previous scenario from updating the currently selected scenario
      const currentRunId = snapshotRef.current?.scenario_run_id ?? null;
      if (
        currentRunId !== null &&
        state.scenario_run_id !== null &&
        state.scenario_run_id !== currentRunId &&
        !noCommandOverlap
      ) {
        return;
      }

      const authoritative = noCommandOverlap;

      // With no command overlapping, if seq went down, backend restarted on a fresh database.
      if (authoritative && state.latest_event_seq < historyCursorRef.current) {
        historyCursorRef.current = 0;
        eventsRef.current = [];
        setEvents([]);
      }

      const applied = applySnapshot(state, authoritative);
      if (!applied) {
        // Snapshot was rejected as older/superseded; do not update dependent state (incidents).
        return;
      }

      lastAppliedRefreshSeqRef.current = reqSeq;
      setIncidents(incidentList.incidents);

      // Catch up on history page by page starting strictly from our pagination cursor.
      // Command responses may have added isolated events to eventsRef, but historyCursorRef
      // strictly advances only when a history page is successfully fetched and processed.
      for (let page = 0; page < 20; page += 1) {
        const history = await client.events(historyCursorRef.current);
        applyEvents(history.events);
        if (history.events.length > 0) {
          const maxPageSeq = history.events[history.events.length - 1].seq;
          if (maxPageSeq > historyCursorRef.current) {
            historyCursorRef.current = maxPageSeq;
          }
        }
        if (
          history.events.length < history.limit ||
          historyCursorRef.current >= history.latest_event_seq
        ) {
          break;
        }
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
      const commandGen = ++commandGenerationRef.current;
      pendingRef.current = label;
      commandEpochRef.current += 1;
      setPending(label);
      try {
        const response = await send();
        // If superseded or timed out, do not apply late results
        if (commandGenerationRef.current !== commandGen) return;

        // A duplicate replay returns the snapshot recorded the FIRST time, which may
        // be stale now — so we only trust fresh responses' snapshots, then re-sync.
        if (!response.duplicate) applySnapshot(response.snapshot);
        // Add events from command response to display list without advancing historyCursorRef
        applyEvents(response.events);
        setOutcome({
          label,
          status: response.duplicate ? "duplicate" : "accepted",
          message: response.message,
          at: Date.now(),
        });
      } catch (error) {
        if (commandGenerationRef.current !== commandGen) return;

        const apiError =
          error instanceof ApiError
            ? error
            : new ApiError("UNCERTAIN_TRANSPORT_ERROR", String(error), 0);

        // A 5xx on a command is NOT a confirmed rejection: the backend failed while
        // handling it, so the command may already have executed. Like a transport failure,
        // its outcome is uncertain, and Retry must resend the SAME body (same command_id)
        // so the backend's deduplication returns the recorded result instead of re-running it.
        const serverError = apiError.status >= 500;
        const isUncertain = apiError.isUncertain || serverError;
        const message = serverError
          ? `${apiError.message} The command may have executed; state is re-syncing, check the audit history. Retrying resends the same command ID.`
          : apiError.message;
        setOutcome({
          label,
          status: isUncertain ? (apiError.isTimeout || serverError ? "uncertain" : "network") : "rejected",
          message,
          code: apiError.code,
          details: apiError.details,
          at: Date.now(),
          retry: isUncertain ? () => void runCommand(label, send) : undefined,
        });
      } finally {
        if (commandGenerationRef.current === commandGen) {
          pendingRef.current = null;
          commandEpochRef.current += 1;
          setPending(null);
        }
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
