import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./api/client";
import type { Api } from "./api/client";
import type { CommandResponse, EventHistoryResponse, SystemSnapshot } from "./api/types";
import { App } from "./App";
import { AeroGuardProvider, useAeroGuard } from "./hooks/useAeroGuard";
import { INCIDENT_ID, RUN_ID, makeClient, makeEvent, makeIncident, makeSnapshot } from "./test/fixtures";

afterEach(() => {
  cleanup();
  window.location.hash = "";
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

let refreshBridge: (() => Promise<void>) | null = null;
function HookBridge() {
  const { refresh } = useAeroGuard();
  refreshBridge = refresh;
  return null;
}

function renderApp(client: Api, hash = "#simulation", pollMs = 60_000) {
  window.location.hash = hash;
  refreshBridge = null;
  return render(
    <AeroGuardProvider client={client} pollMs={pollMs}>
      <HookBridge />
      <App />
    </AeroGuardProvider>,
  );
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("ISSUE 1 REGRESSION: Audit history cursor pagination & event retention", () => {
  it("retrieves previously unfetched events even if a command response carried a higher seq", async () => {
    let currentSeq = 5;
    const historyCalls: number[] = [];

    const eventsMock = vi.fn().mockImplementation((afterSeq: number) => {
      historyCalls.push(afterSeq);
      if (afterSeq === 0) {
        return Promise.resolve<EventHistoryResponse>({
          after_seq: 0,
          events: [makeEvent(1), makeEvent(2), makeEvent(3), makeEvent(4), makeEvent(5)],
          limit: 100,
          latest_event_seq: currentSeq,
        });
      }
      if (afterSeq === 5) {
        // Intermediary events 6..14 generated on backend
        return Promise.resolve<EventHistoryResponse>({
          after_seq: 5,
          events: Array.from({ length: 9 }, (_, i) => makeEvent(i + 6)),
          limit: 100,
          latest_event_seq: currentSeq,
        });
      }
      return Promise.resolve<EventHistoryResponse>({
        after_seq: afterSeq,
        events: [],
        limit: 100,
        latest_event_seq: currentSeq,
      });
    });

    const advanceScenario = vi.fn().mockImplementation(() => {
      currentSeq = 15;
      return Promise.resolve<CommandResponse>({
        command_id: "cmd-advance-15",
        accepted: true,
        duplicate: false,
        message: "Advanced",
        snapshot: makeSnapshot({ latest_event_seq: 15 }),
        events: [makeEvent(15)],
      });
    });

    const client = makeClient(makeSnapshot({ latest_event_seq: 5 }), {
      state: () => Promise.resolve(makeSnapshot({ latest_event_seq: currentSeq })),
      events: eventsMock,
      advanceScenario,
    });

    renderApp(client, "#simulation");

    // Wait for initial history events 1..5 to be loaded
    expect(await screen.findByText("#5")).toBeTruthy();

    // Trigger command that returns seq 15
    const advanceBtn = await screen.findByRole("button", { name: /Advance \+1000 ms/ });
    await act(async () => {
      fireEvent.click(advanceBtn);
    });

    // Verify command event 15 is rendered
    expect(await screen.findByText("#15")).toBeTruthy();

    // Verify history pagination query requested afterSeq=5
    await waitFor(() => {
      expect(historyCalls).toContain(5);
    });

    // Verify intermediary events 6..14 are retrieved and rendered
    expect(await screen.findByText("#6")).toBeTruthy();
    expect(await screen.findByText("#10")).toBeTruthy();
    expect(await screen.findByText("#14")).toBeTruthy();
  });

  it("does not advance history cursor on failed request, and recovers on subsequent poll", async () => {
    let failHistory = true;
    const requestedCursors: number[] = [];

    const eventsMock = vi.fn().mockImplementation((afterSeq: number) => {
      requestedCursors.push(afterSeq);
      if (afterSeq === 0) {
        return Promise.resolve<EventHistoryResponse>({
          after_seq: 0,
          events: [makeEvent(1), makeEvent(2)],
          limit: 2,
          latest_event_seq: 5,
        });
      }
      if (afterSeq === 2) {
        if (failHistory) {
          return Promise.reject(new ApiError("NETWORK_ERROR", "Temporary network failure", 0));
        }
        return Promise.resolve<EventHistoryResponse>({
          after_seq: 2,
          events: [makeEvent(3), makeEvent(4), makeEvent(5)],
          limit: 100,
          latest_event_seq: 5,
        });
      }
      return Promise.resolve<EventHistoryResponse>({
        after_seq: afterSeq,
        events: [],
        limit: 100,
        latest_event_seq: 5,
      });
    });

    const client = makeClient(makeSnapshot({ latest_event_seq: 5 }), { events: eventsMock });
    renderApp(client, "#simulation", 40);

    // Initial page fetched (event 2)
    expect(await screen.findByText("#2")).toBeTruthy();

    // Cursor 2 was requested and failed
    await waitFor(() => {
      expect(requestedCursors).toContain(2);
    });

    // Now permit history to succeed on subsequent poll
    failHistory = false;

    // After recovery, cursor 2 is requested again and missed events 3, 4, 5 are processed
    expect(await screen.findByText("#5")).toBeTruthy();
    expect(screen.getByText("#3")).toBeTruthy();
    expect(screen.getByText("#4")).toBeTruthy();
  });

  it("does not introduce duplicates on repeated polling", async () => {
    const snapshot = makeSnapshot({ latest_event_seq: 3 });
    const eventsMock = vi.fn().mockResolvedValue({
      after_seq: 0,
      events: [makeEvent(1), makeEvent(2), makeEvent(3)],
      limit: 100,
      latest_event_seq: 3,
    });

    const client = makeClient(snapshot, { events: eventsMock });
    renderApp(client, "#simulation", 25);

    expect(await screen.findByText("#1")).toBeTruthy();
    expect(screen.getByText("#2")).toBeTruthy();
    expect(screen.getByText("#3")).toBeTruthy();

    // Verify exactly one DOM element per seq exists
    expect(screen.getAllByText("#1")).toHaveLength(1);
    expect(screen.getAllByText("#2")).toHaveLength(1);
    expect(screen.getAllByText("#3")).toHaveLength(1);
  });

  it("does not incorrectly attribute events from a previous scenario to the current scenario", async () => {
    const runOld = "11111111-0000-0000-0000-000000000000";
    const runNew = "22222222-0000-0000-0000-000000000000";

    const eventsMock = vi.fn().mockResolvedValue({
      after_seq: 0,
      events: [
        makeEvent(1, { scenario_run_id: runOld }),
        makeEvent(2, { scenario_run_id: runOld }),
        makeEvent(3, { scenario_run_id: runNew }),
      ],
      limit: 100,
      latest_event_seq: 3,
    });

    const client = makeClient(makeSnapshot({ scenario_run_id: runNew, latest_event_seq: 3 }), {
      events: eventsMock,
    });

    renderApp(client, "#simulation");

    // By default, current run filter shows only events for runNew
    expect(await screen.findByText("#3")).toBeTruthy();
    expect(screen.queryByText("#1")).toBeNull();
    expect(screen.queryByText("#2")).toBeNull();

    // Clicking "All runs" shows both runs
    fireEvent.click(screen.getByRole("button", { name: "All runs" }));
    expect(await screen.findByText("#1")).toBeTruthy();
    expect(screen.getByText("#2")).toBeTruthy();
    expect(screen.getByText("#3")).toBeTruthy();
  });
});

describe("ISSUE 2 REGRESSION: Out-of-order refreshes and state consistency", () => {
  it("rejects delayed older refresh response from overwriting newer snapshot", async () => {
    const initial = makeSnapshot({
      latest_event_seq: 5,
      guardian_state: "NORMAL",
      status_text: "Initial",
    });
    const snapshotNew = makeSnapshot({
      latest_event_seq: 20,
      guardian_state: "ESCALATED",
      status_text: "New State",
    });
    const snapshotOld = makeSnapshot({
      latest_event_seq: 10,
      guardian_state: "NORMAL",
      status_text: "Old State",
    });

    const oldDefer = deferred<SystemSnapshot>();
    const newDefer = deferred<SystemSnapshot>();

    let triggerCount = 0;
    const stateMock = vi.fn().mockImplementation(() => {
      triggerCount += 1;
      if (triggerCount === 1) return Promise.resolve(initial); // Initial mount
      if (triggerCount === 2) return oldDefer.promise; // Request 1: delayed
      return newDefer.promise; // Request 2: resolves first
    });

    const client = makeClient(initial, { state: stateMock });
    renderApp(client, "#simulation", 60_000);

    // Initial load
    expect(await screen.findByText("Guardian Normal")).toBeTruthy();

    // Trigger concurrent refreshes via the bridge
    const p1 = refreshBridge!(); // reqSeq 1 (delayed)
    const p2 = refreshBridge!(); // reqSeq 2 (fast)

    // Resolve Request 2 first with newer snapshot
    await act(async () => {
      newDefer.resolve(snapshotNew);
      await p2;
    });

    expect(await screen.findByText("Guardian Escalated")).toBeTruthy();

    // Now resolve Request 1 with older snapshot
    await act(async () => {
      oldDefer.resolve(snapshotOld);
      await p1;
    });

    // Newer snapshot MUST NOT be overwritten by older snapshot
    expect(screen.getByText("Guardian Escalated")).toBeTruthy();
    expect(screen.queryByText("Guardian Normal")).toBeNull();
  });

  it("prevents delayed refresh from restoring outdated ATC controls and incidents", async () => {
    const runId = RUN_ID;
    const incident = makeIncident({ incident_id: INCIDENT_ID, scenario_run_id: runId });

    // Initial state: AWAITING_ATC with active incident
    const stateInit = makeSnapshot({
      scenario_run_id: runId,
      sentinel_state: "AWAITING_ATC",
      active_incident: incident,
      latest_event_seq: 15,
    });

    // Newer state: authorization COMPLETED and active incident resolved
    const stateNew = makeSnapshot({
      scenario_run_id: runId,
      sentinel_state: "COMPLETED",
      active_incident: null,
      latest_event_seq: 25,
    });

    // Outdated state: older seq 15
    const stateOld = makeSnapshot({
      scenario_run_id: runId,
      sentinel_state: "AWAITING_ATC",
      active_incident: incident,
      latest_event_seq: 15,
    });

    const oldDefer = deferred<SystemSnapshot>();
    const newDefer = deferred<SystemSnapshot>();

    let count = 0;
    const stateMock = vi.fn().mockImplementation(() => {
      count += 1;
      if (count === 1) return Promise.resolve(stateInit); // Initial mount
      if (count === 2) return oldDefer.promise; // Delayed poll
      return newDefer.promise; // Fast poll
    });

    const client = makeClient(stateInit, {
      state: stateMock,
      incidents: () => Promise.resolve({ incidents: count === 1 || count === 2 ? [incident] : [] }),
    });

    renderApp(client, "#atc", 60_000);

    // Initial load confirms Awaiting ATC
    expect(await screen.findByRole("button", { name: /Approve SIM_STABILIZE/ })).toBeTruthy();

    // Trigger concurrent refreshes
    const p1 = refreshBridge!();
    const p2 = refreshBridge!();

    // Resolve newer state first
    await act(async () => {
      newDefer.resolve(stateNew);
      await p2;
    });

    // Decision blocker shows Sentinel has no active incident awaiting decision
    await waitFor(() => {
      expect(screen.getByTestId("decision-blocker").textContent).toMatch(/No active incident|not awaiting/);
    });

    // Now resolve older state
    await act(async () => {
      oldDefer.resolve(stateOld);
      await p1;
    });

    // Outdated controls MUST NOT be restored
    expect(screen.getByTestId("decision-blocker").textContent).toMatch(/No active incident|not awaiting/);
    const approveBtn = screen.getByRole("button", { name: /Approve/ });
    expect((approveBtn as HTMLButtonElement).disabled).toBe(true);
  });

  it("ignores in-flight refresh for previous scenario after scenario switch", async () => {
    const runOld = "11111111-0000-0000-0000-000000000000";
    const runNew = "22222222-0000-0000-0000-000000000000";

    const oldScenarioDefer = deferred<SystemSnapshot>();
    let count = 0;
    const stateMock = vi.fn().mockImplementation(() => {
      count += 1;
      if (count === 1) return Promise.resolve(makeSnapshot({ scenario_run_id: runOld }));
      if (count === 2) return oldScenarioDefer.promise;
      return Promise.resolve(makeSnapshot({ scenario_run_id: runNew, scenario_id: "normal_flight", latest_event_seq: 2 }));
    });

    const startScenarioMock = vi.fn().mockResolvedValue({
      command_id: "start-new-scenario",
      accepted: true,
      duplicate: false,
      message: "Started normal_flight",
      snapshot: makeSnapshot({ scenario_run_id: runNew, scenario_id: "normal_flight", latest_event_seq: 1 }),
      events: [makeEvent(1, { scenario_run_id: runNew })],
    });

    const client = makeClient(makeSnapshot({ scenario_run_id: runOld }), {
      state: stateMock,
      startScenario: startScenarioMock,
    });

    renderApp(client, "#simulation", 60_000);

    // Initial load shows old run
    expect((await screen.findAllByText(new RegExp(runOld.slice(0, 8)))).length).toBeGreaterThan(0);

    // Trigger an in-flight refresh for old run
    const inFlightOldPoll = refreshBridge!();

    // User selects normal_flight radio and starts new scenario
    fireEvent.click(screen.getByDisplayValue("normal_flight"));
    const startBtn = await screen.findByRole("button", { name: /Start selected scenario/i });
    await act(async () => {
      fireEvent.click(startBtn);
    });

    // Old in-flight refresh resolves now
    await act(async () => {
      oldScenarioDefer.resolve(makeSnapshot({ scenario_run_id: runOld, scenario_id: "dual_pilot_atc_connected", latest_event_seq: 50 }));
      await inFlightOldPoll;
    });

    // UI should retain new scenario runNew
    expect((await screen.findAllByText(new RegExp(runNew.slice(0, 8)))).length).toBeGreaterThan(0);
  });

  it("recovers cleanly from failed refreshes without leaving UI permanently loading", async () => {
    let failState = true;
    const stateMock = vi.fn().mockImplementation(() => {
      if (failState) {
        return Promise.reject(new ApiError("NETWORK_ERROR", "Backend offline", 0));
      }
      return Promise.resolve(makeSnapshot({ latest_event_seq: 10, guardian_state: "NORMAL" }));
    });

    const client = makeClient(makeSnapshot(), { state: stateMock });
    renderApp(client, "#simulation", 30);

    // Initial failure shows offline warning
    expect(await screen.findByText(/Backend unreachable/)).toBeTruthy();

    // Now backend comes back online
    failState = false;

    // Recovers automatically without remaining in offline warning
    await waitFor(() => {
      expect(screen.queryByText(/Backend unreachable/)).toBeNull();
    });
    expect(screen.getByText(/Backend online/)).toBeTruthy();
  });
});

describe("ISSUE 3 REGRESSION: Transport failures classified as uncertain & retry identity", () => {
  it("classifies response body streaming failure as uncertain with retry preserving command_id", async () => {
    let capturedCommandId: string | null = null;
    let callCount = 0;

    const advanceScenario = vi.fn().mockImplementation((body: { command_id: string }) => {
      callCount += 1;
      capturedCommandId = body.command_id;
      if (callCount === 1) {
        // Transport error reading body: uncertain execution
        return Promise.reject(new ApiError("UNCERTAIN_TRANSPORT_ERROR", "Stream closed prematurely", 200));
      }
      return Promise.resolve<CommandResponse>({
        command_id: body.command_id,
        accepted: true,
        duplicate: false,
        message: "Advance confirmed on retry",
        snapshot: makeSnapshot({ latest_event_seq: 10 }),
        events: [makeEvent(10)],
      });
    });

    const client = makeClient(makeSnapshot(), { advanceScenario });
    renderApp(client, "#simulation");

    const advanceBtn = await screen.findByRole("button", { name: /Advance \+1000 ms/ });
    await act(async () => {
      fireEvent.click(advanceBtn);
    });

    // Outcome must be uncertain/transport error, NOT "Rejected by backend"
    expect(await screen.findByText(/command outcome (unknown|uncertain)/i)).toBeTruthy();
    expect(screen.queryByText(/Rejected by backend/)).toBeNull();

    const originalCommandId = capturedCommandId;
    expect(originalCommandId).toBeTruthy();

    // Retry button is available
    const retryBtn = screen.getByRole("button", { name: /Retry same command/i });
    await act(async () => {
      fireEvent.click(retryBtn);
    });

    // Exactly the same command_id is reused on retry
    expect(advanceScenario).toHaveBeenCalledTimes(2);
    expect(capturedCommandId).toBe(originalCommandId);
    expect(await screen.findByText(/Advance confirmed on retry/)).toBeTruthy();
  });

  it("distinguishes confirmed backend rejection and does not offer duplicate resubmission retry", async () => {
    const atcDecision = vi.fn().mockRejectedValue(
      new ApiError("AUTHORIZATION_REJECTED", "Simulated ATC rejected by Sentinel policy", 409, ["Peer responsive"]),
    );

    const client = makeClient(
      makeSnapshot({ active_incident: makeIncident(), sentinel_state: "AWAITING_ATC" }),
      { atcDecision },
    );

    renderApp(client, "#atc");

    const approveBtn = await screen.findByRole("button", { name: /Approve SIM_STABILIZE/ });
    await act(async () => {
      fireEvent.click(approveBtn);
    });

    // Classified as confirmed rejection
    expect(await screen.findByText(/Rejected by backend/)).toBeTruthy();
    expect(screen.getByText(/AUTHORIZATION_REJECTED/)).toBeTruthy();

    // No retry button offered for confirmed rejections
    expect(screen.queryByRole("button", { name: /Retry same command/i })).toBeNull();
  });
});

describe("ISSUE 4 REGRESSION: Bounded request timeout & command lock recovery", () => {
  it("releases command lock upon timeout and permits subsequent recovery actions like reset", async () => {
    let capturedTimeoutCommandId: string | null = null;
    const advanceScenario = vi.fn().mockImplementation((body: { command_id: string }) => {
      capturedTimeoutCommandId = body.command_id;
      // Stalled request that times out
      return Promise.reject(new ApiError("TIMEOUT_ERROR", "Request timed out after 5000ms — backend status uncertain", 0));
    });

    const resetScenario = vi.fn().mockResolvedValue({
      command_id: "reset-cmd-id",
      accepted: true,
      duplicate: false,
      message: "Reset successful",
      snapshot: makeSnapshot({ latest_event_seq: 1, scenario_run_id: "reset-run-id" }),
      events: [makeEvent(1, { scenario_run_id: "reset-run-id" })],
    });

    const client = makeClient(makeSnapshot(), { advanceScenario, resetScenario });
    renderApp(client, "#simulation");

    const advanceBtn = await screen.findByRole("button", { name: /Advance \+1000 ms/ });
    await act(async () => {
      fireEvent.click(advanceBtn);
    });

    expect(capturedTimeoutCommandId).toBeTruthy();

    // Timeout outcome shown
    expect(await screen.findByText(/command outcome (unknown|uncertain)/i)).toBeTruthy();

    // Command lock is released: Reset button is not blocked
    const resetBtn = screen.getByRole("button", { name: /Reset run/ });
    await act(async () => {
      fireEvent.click(resetBtn);
    });

    // Reset executes successfully
    await waitFor(() => {
      expect(resetScenario).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText(/Reset successful/)).toBeTruthy();
  });

  it("discards the late response of a timed-out command instead of overwriting newer state or the lock", async () => {
    // Exercises the real transport: advanceScenario goes through api.advanceScenario
    // (request() with its AbortController timeout) against a stubbed fetch that behaves
    // like a browser — it rejects when aborted, and the server's answer can still arrive later.
    const sentCommandIds: string[] = [];
    let firstSignal: AbortSignal | null = null;
    const lateFirstResponse = deferred<Response>();
    const commandResponse = (body: CommandResponse) => new Response(JSON.stringify(body), { status: 200 });

    const fetchMock = vi.fn((_url: string, init: RequestInit) => {
      sentCommandIds.push((JSON.parse(String(init.body)) as { command_id: string }).command_id);
      if (sentCommandIds.length === 1) {
        firstSignal = init.signal ?? null;
        return new Promise<Response>((resolve, reject) => {
          init.signal?.addEventListener("abort", () => reject(new DOMException("The operation was aborted.", "AbortError")));
          void lateFirstResponse.promise.then(resolve);
        });
      }
      return Promise.resolve(
        commandResponse({
          command_id: sentCommandIds[1],
          accepted: true,
          duplicate: false,
          message: "Second command executed",
          snapshot: makeSnapshot({ latest_event_seq: 99 }),
          events: [makeEvent(99)],
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const advanceScenario: Api["advanceScenario"] = (body) => api.advanceScenario(body, { timeoutMs: 50 });
    const client = makeClient(makeSnapshot(), { advanceScenario });
    renderApp(client, "#simulation");

    const advanceBtn = (await screen.findByRole("button", { name: /Advance \+1000 ms/ })) as HTMLButtonElement;

    // Command 1 never answers in time: request() aborts it and reports an uncertain outcome.
    fireEvent.click(advanceBtn);
    expect(await screen.findByText(/command outcome (unknown|uncertain)/i)).toBeTruthy();
    expect(firstSignal).not.toBeNull();
    expect(firstSignal!.aborted).toBe(true);

    // The pending-command lock was released, so command 2 can run and its state applies.
    await waitFor(() => expect(advanceBtn.disabled).toBe(false));
    fireEvent.click(advanceBtn);
    expect(await screen.findByText(/Second command executed/)).toBeTruthy();
    expect(screen.getByText("#99")).toBeTruthy();
    expect(sentCommandIds).toHaveLength(2);
    expect(sentCommandIds[1]).not.toBe(sentCommandIds[0]);

    // The backend's answer to command 1 now arrives, carrying an older snapshot and event.
    await act(async () => {
      lateFirstResponse.resolve(
        commandResponse({
          command_id: sentCommandIds[0],
          accepted: true,
          duplicate: false,
          message: "Late first command",
          snapshot: makeSnapshot({ latest_event_seq: 50 }),
          events: [makeEvent(50)],
        }),
      );
      await lateFirstResponse.promise;
    });

    // Nothing from the late response is applied: outcome, state, history and lock are unchanged.
    expect(screen.getByText(/Second command executed/)).toBeTruthy();
    expect(screen.queryByText(/Late first command/)).toBeNull();
    expect(screen.getByText("#99")).toBeTruthy();
    expect(screen.queryByText("#50")).toBeNull();
    expect(advanceBtn.disabled).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
