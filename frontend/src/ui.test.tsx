import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Api } from "./api/client";
import type { CommandResponse } from "./api/types";
import { App, SIMULATION_NOTICE } from "./App";
import { AeroGuardProvider, isNewerSnapshot } from "./hooks/useAeroGuard";
import { BlackBoxPage } from "./pages/BlackBoxPage";
import { FlightDeckPage } from "./pages/FlightDeckPage";
import { GuardianPage } from "./pages/GuardianPage";
import { ScenariosPage } from "./pages/ScenariosPage";
import { decisionBlocker, SentinelPage } from "./pages/SentinelPage";
import { VisionPage } from "./pages/VisionPage";
import { INCIDENT_ID, RUN_ID, SCENARIOS, makeClient, makeEvent, makeIncident, makeSnapshot } from "./test/fixtures";

afterEach(() => {
  cleanup();
  window.location.hash = "";
});

function renderWith(ui: React.ReactElement, client: Api) {
  return render(
    <AeroGuardProvider client={client} pollMs={60_000}>
      {ui}
    </AeroGuardProvider>,
  );
}

function response(overrides: Partial<CommandResponse> = {}): CommandResponse {
  return { command_id: "c", accepted: true, duplicate: false, message: "ok", snapshot: makeSnapshot(), events: [], ...overrides };
}

describe("snapshot freshness", () => {
  it("rejects a snapshot older than the one held", () => {
    expect(isNewerSnapshot(makeSnapshot({ latest_event_seq: 10 }), makeSnapshot({ latest_event_seq: 9 }))).toBe(false);
    expect(isNewerSnapshot(makeSnapshot({ latest_event_seq: 10 }), makeSnapshot({ latest_event_seq: 10 }))).toBe(true);
    expect(isNewerSnapshot(null, makeSnapshot())).toBe(true);
  });
});

describe("decisionBlocker (ATC control enablement)", () => {
  const awaiting = makeSnapshot({ sentinel_state: "AWAITING_ATC", active_incident: makeIncident() });
  it("allows a decision only while Sentinel awaits ATC with a connected link and active incident", () => {
    expect(decisionBlocker(awaiting, null)).toBeNull();
    expect(decisionBlocker({ ...awaiting, sentinel_state: "STANDBY" }, null)).toMatch(/not awaiting/);
    expect(decisionBlocker({ ...awaiting, active_incident: null }, null)).toMatch(/No active incident/);
    expect(decisionBlocker({ ...awaiting, communication: { ...awaiting.communication, atc_link_connected: false } }, null)).toMatch(/disconnected/);
    expect(decisionBlocker({ ...awaiting, scenario_run_id: null }, null)).toMatch(/No active scenario/);
    expect(decisionBlocker(awaiting, "Advance")).toMatch(/in flight/);
  });
});

describe("App shell", () => {
  it("always shows the simulation-only notice", async () => {
    renderWith(<App />, makeClient(makeSnapshot()));
    expect((await screen.findAllByText(SIMULATION_NOTICE)).length).toBeGreaterThan(0);
  });

  it("reports an unreachable backend instead of fake data", async () => {
    const { ApiError } = await import("./api/client");
    const down = () => Promise.reject(new ApiError("NETWORK_ERROR", "down", 0));
    renderWith(<App />, makeClient(makeSnapshot(), { state: down, incidents: down }));
    expect(await screen.findByText(/Backend unreachable\./)).toBeTruthy();
  });
});

describe("ScenariosPage", () => {
  it("renders every canonical scenario from the API catalogue", async () => {
    renderWith(<ScenariosPage />, makeClient(makeSnapshot()));
    for (const s of SCENARIOS) expect((await screen.findAllByText(s.scenario_id)).length).toBeGreaterThan(0);
    expect(screen.queryByText(/missing canonical scenarios/)).toBeNull();
  });

  it("sends Advance with the active run ID and a fresh command ID", async () => {
    const advanceScenario = vi.fn().mockResolvedValue(response({ message: "Advanced virtual time by 1000 ms" }));
    renderWith(<ScenariosPage />, makeClient(makeSnapshot(), { advanceScenario }));
    const button = await screen.findByRole("button", { name: /Advance \+1000 ms/ });
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(button);
    await waitFor(() => expect(advanceScenario).toHaveBeenCalledTimes(1));
    const body = advanceScenario.mock.calls[0][0];
    expect(body.scenario_run_id).toBe(RUN_ID);
    expect(body.delta_ms).toBe(1000);
    expect(body.command_id).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("ignores a second click while the first command is in flight", async () => {
    let resolve!: (r: CommandResponse) => void;
    const advanceScenario = vi.fn().mockImplementation(() => new Promise<CommandResponse>((r) => (resolve = r)));
    renderWith(<ScenariosPage />, makeClient(makeSnapshot(), { advanceScenario }));
    const button = await screen.findByRole("button", { name: /Advance \+1000 ms/ });
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(button);
    fireEvent.click(button);
    expect(advanceScenario).toHaveBeenCalledTimes(1);
    await act(async () => resolve(response()));
  });
});

describe("GuardianPage", () => {
  it("acknowledges with alert_id bound to the active incident", async () => {
    const acknowledge = vi.fn().mockResolvedValue(response());
    const snapshot = makeSnapshot({ guardian_state: "AWAITING_ACK", active_incident: makeIncident({ incident_type: "PILOT_RESPONSE_REQUIRED", severity: "WARNING" }) });
    renderWith(<GuardianPage />, makeClient(snapshot, { acknowledge }));
    fireEvent.click(await screen.findByRole("button", { name: "Acknowledge as Pilot 1" }));
    await waitFor(() => expect(acknowledge).toHaveBeenCalledTimes(1));
    expect(acknowledge.mock.calls[0][0]).toMatchObject({ pilot_id: "PILOT_1", alert_id: INCIDENT_ID, scenario_run_id: RUN_ID });
  });

  it("labels missing observations honestly", async () => {
    renderWith(<GuardianPage />, makeClient(makeSnapshot()));
    expect((await screen.findAllByText(/No observation received/)).length).toBe(2);
  });
});

describe("SentinelPage (fictional ATC)", () => {
  it("disables Approve/Reject when Sentinel is not awaiting ATC", async () => {
    renderWith(<SentinelPage />, makeClient(makeSnapshot({ active_incident: makeIncident(), sentinel_state: "STANDBY" })));
    const approve = await screen.findByRole("button", { name: /Approve/ });
    expect((approve as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByTestId("decision-blocker").textContent).toMatch(/not awaiting/);
  });

  it("shows success only after the backend confirms, and surfaces rejections", async () => {
    const { ApiError } = await import("./api/client");
    const atcDecision = vi.fn().mockRejectedValue(new ApiError("AUTHORIZATION_REJECTED", "Sentinel rejected", 409));
    const snapshot = makeSnapshot({ active_incident: makeIncident(), sentinel_state: "AWAITING_ATC" });
    renderWith(<SentinelPage />, makeClient(snapshot, { atcDecision }));
    const approve = await screen.findByRole("button", { name: /Approve SIM_STABILIZE/ });
    await waitFor(() => expect((approve as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(approve);
    await waitFor(() => expect(atcDecision).toHaveBeenCalledTimes(1));
    expect(atcDecision.mock.calls[0][0]).toMatchObject({
      decision: "APPROVE",
      requested_action: "SIM_STABILIZE",
      incident_id: INCIDENT_ID,
      scenario_run_id: RUN_ID,
    });
  });

  it("never offers NO_OP as an approvable action", async () => {
    renderWith(<SentinelPage />, makeClient(makeSnapshot({ active_incident: makeIncident(), sentinel_state: "AWAITING_ATC" })));
    await screen.findByRole("button", { name: /Approve/ });
    expect(screen.queryByRole("option", { name: "NO_OP" })).toBeNull();
  });
});

describe("backend restart on a fresh database", () => {
  it("accepts an idle snapshot with a LOWER seq when no command overlapped the poll", async () => {
    let current = makeSnapshot({ latest_event_seq: 30, guardian_state: "ESCALATED" });
    const client = makeClient(current, { state: () => Promise.resolve(current) });
    const view = render(
      <AeroGuardProvider client={client} pollMs={20}>
        <App />
      </AeroGuardProvider>,
    );
    expect(await screen.findByText("Guardian Escalated")).toBeTruthy();
    current = makeSnapshot({ latest_event_seq: 0, scenario_id: null, scenario_run_id: null, virtual_time: null });
    expect(await screen.findByText("Guardian Normal")).toBeTruthy();
    view.unmount();
  });
});

describe("duplicate command responses", () => {
  it("does not apply the stale snapshot recorded with a duplicate", async () => {
    const fresh = makeSnapshot({ latest_event_seq: 20, guardian_state: "ESCALATED" });
    const staleDuplicate = response({ duplicate: true, message: "Duplicate command: x", snapshot: makeSnapshot({ latest_event_seq: 20, guardian_state: "NORMAL" }) });
    const advanceScenario = vi.fn().mockResolvedValue(staleDuplicate);
    renderWith(<App />, makeClient(fresh, { advanceScenario }));
    window.location.hash = "#simulation";
    const button = await screen.findByRole("button", { name: /Advance \+1000 ms/ });
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(button);
    expect(await screen.findByText(/Duplicate command — backend returned the original result/)).toBeTruthy();
    expect(screen.getByText("Guardian Escalated")).toBeTruthy();
  });
});

describe("redesigned shell and consoles", () => {
  it("marks the current view in the navigation and flags a pending ATC decision", async () => {
    window.location.hash = "#atc"; // legacy link still opens the Sentinel / fictional ATC view
    renderWith(<App />, makeClient(makeSnapshot({ sentinel_state: "AWAITING_ATC", active_incident: makeIncident() })));
    const current = await screen.findByRole("link", { current: "page" });
    expect(current.textContent).toContain("Sentinel");
    expect(await screen.findByRole("link", { name: "Sentinel (Decision required)" })).toBeTruthy();
  });

  it("shows the ATC authorization status derived from Sentinel's decisions", async () => {
    const snapshot = makeSnapshot({ sentinel_state: "AWAITING_ATC", active_incident: makeIncident() });
    const rejected = {
      seq: 7,
      event_id: "00000000-0000-4000-8000-000000000007",
      schema_version: "1.0" as const,
      event_type: "SENTINEL_DECISION" as const,
      occurred_at: "2026-01-01T00:00:02Z",
      source: "SENTINEL" as const,
      scenario_run_id: RUN_ID,
      correlation_id: RUN_ID,
      causation_event_id: null,
      payload: {
        decision_id: "d7",
        incident_id: INCIDENT_ID,
        scenario_run_id: RUN_ID,
        sentinel_state: "AWAITING_ATC" as const,
        action_type: "NO_OP" as const,
        authorization_source: "SIMULATED_ATC" as const,
        reason: "Simulated ATC rejected the requested action; no action executed.",
        evidence_event_ids: [],
        executed_at: "2026-01-01T00:00:02Z",
        result: "REJECTED" as const,
      },
    };
    const client = makeClient(snapshot, {
      events: (afterSeq: number) => Promise.resolve({ after_seq: afterSeq, events: afterSeq < 7 ? [rejected] : [], latest_event_seq: 7, limit: 500 }),
    });
    renderWith(<SentinelPage />, client);
    expect(await screen.findByText("Rejected", { selector: ".auth-status__title" })).toBeTruthy();
    expect(screen.getByText(/Sentinel is still awaiting a valid decision/)).toBeTruthy();
    // Rejection is not authorization: approval stays available while Sentinel awaits ATC.
    expect((screen.getByRole("button", { name: /Approve SIM_STABILIZE/ }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("toggles the simulated ATC link through the backend command with the active run ID", async () => {
    const setLink = vi.fn().mockResolvedValue(response());
    renderWith(<ScenariosPage />, makeClient(makeSnapshot(), { setLink }));
    const toggle = await screen.findByRole("switch", { name: "Simulated ATC link connected" });
    await waitFor(() => expect((toggle as HTMLButtonElement).disabled).toBe(false));
    expect(toggle.getAttribute("aria-checked")).toBe("true");
    fireEvent.click(toggle);
    await waitFor(() => expect(setLink).toHaveBeenCalledTimes(1));
    expect(setLink.mock.calls[0][0]).toMatchObject({ scenario_run_id: RUN_ID, atc_link_connected: false });
  });
});

describe("attention indicators", () => {
  it("does not flag an ATC decision once the incident has been cleared", async () => {
    window.location.hash = "#guardian";
    // Sentinel can remain AWAITING_ATC after an acknowledgement clears the incident (mock behaviour);
    // no decision is possible then, so the navigation must not ask for one.
    renderWith(<App />, makeClient(makeSnapshot({ sentinel_state: "AWAITING_ATC", active_incident: null, guardian_state: "RECOVERING" })));
    expect((await screen.findAllByText(/Guardian state is Recovering and there is no active incident/)).length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: "Sentinel (Decision required)" })).toBeNull();
    expect(screen.getByRole("link", { name: "Sentinel" })).toBeTruthy();
  });
});

describe("review regressions", () => {
  it("never reports an eye state the camera could not observe", async () => {
    const snapshot = makeSnapshot({
      pilots: [
        {
          pilot_id: "PILOT_1",
          latest_observation: {
            pilot_id: "PILOT_1",
            observed_at: "2026-01-01T00:00:01Z",
            observation_status: "UNKNOWN",
            camera_available: false,
            face_visible: false,
            eyes_closed: false,
            observation_duration_ms: 1000,
            observation_quality: 0,
          },
        },
        { pilot_id: "PILOT_2", latest_observation: null },
      ],
    });
    renderWith(<VisionPage />, makeClient(snapshot));
    expect((await screen.findAllByText("Not observable")).length).toBeGreaterThan(0);
    expect(screen.queryByText("Open")).toBeNull();
    expect(screen.getByText(/camera unavailable or face not visible/)).toBeTruthy();
  });

  it("shows no all-clear status before any backend state has loaded", async () => {
    const never = () => new Promise<never>(() => undefined);
    renderWith(<App />, makeClient(makeSnapshot(), { state: never, incidents: never }));
    expect((await screen.findAllByText("Waiting for state…")).length).toBeGreaterThan(0);
    expect(screen.queryByText("No active incident")).toBeNull();
  });

  it("announces a poll failure neutrally, without claiming a command partly applied", async () => {
    const { ApiError } = await import("./api/client");
    const fail = () => Promise.reject(new ApiError("HTTP_500", "Backend internal error (HTTP 500).", 500));
    renderWith(<App />, makeClient(makeSnapshot(), { state: fail }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Backend internal error (HTTP 500).");
    expect(alert.textContent).not.toMatch(/may have executed|partly applied/);
  });

  it("warns that a command hit by a 5xx may have executed", async () => {
    const { ApiError } = await import("./api/client");
    const advanceScenario = vi.fn().mockRejectedValue(new ApiError("HTTP_500", "Backend internal error (HTTP 500).", 500));
    window.location.hash = "#simulation";
    renderWith(<App />, makeClient(makeSnapshot(), { advanceScenario }));
    const button = await screen.findByRole("button", { name: /Advance \+1000 ms/ });
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(button);
    expect(await screen.findByText(/The command may have executed/)).toBeTruthy();
  });

  it("labels a pending Sentinel request as awaiting a decision", async () => {
    const snapshot = makeSnapshot({ sentinel_state: "AWAITING_ATC", active_incident: makeIncident() });
    renderWith(<SentinelPage />, makeClient(snapshot));
    expect(await screen.findByText("Awaiting decision", { selector: ".auth-status__title" })).toBeTruthy();
  });

  it("gives every view link an accessible name", async () => {
    renderWith(<App />, makeClient(makeSnapshot()));
    for (const name of ["Flight Deck", "Guardian", "Sentinel", "Vision", "Black Box", "Scenarios"]) {
      expect(await screen.findByRole("link", { name })).toBeTruthy();
    }
  });
});

describe("Flight Deck", () => {
  it("presents a calm NORMAL status from a run without incidents", async () => {
    renderWith(<FlightDeckPage />, makeClient(makeSnapshot({ guardian_state: "NORMAL" })));
    expect(await screen.findByText("Normal", { selector: ".fstatus__value" })).toBeTruthy();
    expect(screen.queryByRole("group", { name: "Guardian escalation" })).toBeNull();
  });

  it("switches to the EMERGENCY treatment only when the backend reports an active incident", async () => {
    const acknowledge = vi.fn().mockResolvedValue(response());
    const snapshot = makeSnapshot({ guardian_state: "ESCALATED", sentinel_state: "AWAITING_ATC", active_incident: makeIncident() });
    renderWith(<FlightDeckPage />, makeClient(snapshot, { acknowledge }));
    expect(await screen.findByText("Emergency", { selector: ".fstatus__value" })).toBeTruthy();
    const panel = screen.getByRole("group", { name: "Guardian escalation" });
    expect(panel.textContent).toContain("Awaiting ATC decision");
    expect(screen.getByRole("link", { name: /Open Sentinel console/ }).getAttribute("href")).toBe("#sentinel");
    fireEvent.click(screen.getByRole("button", { name: "Acknowledge as Pilot 2" }));
    await waitFor(() => expect(acknowledge).toHaveBeenCalledTimes(1));
    expect(acknowledge.mock.calls[0][0]).toMatchObject({ pilot_id: "PILOT_2", alert_id: INCIDENT_ID });
  });

  it("labels the scene as synthetic and never invents engine, fuel or weather data", async () => {
    renderWith(<FlightDeckPage />, makeClient(makeSnapshot()));
    expect(await screen.findByText(/Synthetic scene · illustrative route/)).toBeTruthy();
    expect(screen.queryByText(/ENG 1|FUEL|Weather|Boeing|A320/i)).toBeNull();
  });
});

describe("Black Box replay", () => {
  it("steps through committed events and shows the selected one", async () => {
    const events = [1, 2, 3].map((seq) => makeEvent(seq));
    const client = makeClient(makeSnapshot({ latest_event_seq: 3 }), {
      events: (afterSeq: number) => Promise.resolve({ after_seq: afterSeq, events: afterSeq < 3 ? events : [], latest_event_seq: 3, limit: 500 }),
    });
    renderWith(<BlackBoxPage />, client);
    expect(await screen.findByText(/Event 3 \/ 3/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Previous event" }));
    expect(await screen.findByText(/Event 2 \/ 3/)).toBeTruthy();
    expect(screen.getByText("seq 2")).toBeTruthy();
    expect(screen.getByText(/no video is recorded/i)).toBeTruthy();
  });
});

describe("Sentinel console", () => {
  it("marks the action the simulator actually executed and locks decisions once completed", async () => {
    const snapshot = makeSnapshot({
      sentinel_state: "COMPLETED",
      active_incident: makeIncident(),
      last_simulator_action: {
        action_id: "a1",
        scenario_run_id: RUN_ID,
        action_type: "SIM_STABILIZE",
        authorization_source: "SIMULATED_ATC",
        authorized: true,
        result: "EXECUTED",
        reason: "Validated symbolic simulation action; no operational aircraft control.",
        applied_at: "2026-01-01T00:00:02Z",
      },
    });
    renderWith(<SentinelPage />, makeClient(snapshot));
    expect((await screen.findAllByText(/Executed 00:00:02/)).length).toBeGreaterThan(0);
    expect((screen.getByRole("button", { name: /Approve/ }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole("radio", { name: /NO_OP/ })).toBeNull();
  });
});

describe("Vision", () => {
  it("shows the raw observation fields for each pilot", async () => {
    const snapshot = makeSnapshot({
      pilots: [
        {
          pilot_id: "PILOT_1",
          latest_observation: {
            pilot_id: "PILOT_1",
            observed_at: "2026-01-01T00:00:01Z",
            observation_status: "RESPONSIVE",
            camera_available: true,
            face_visible: true,
            eyes_closed: false,
            observation_duration_ms: 1000,
            observation_quality: 0.93,
          },
        },
        { pilot_id: "PILOT_2", latest_observation: null },
      ],
    });
    renderWith(<VisionPage />, makeClient(snapshot));
    expect((await screen.findAllByText("0.93")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Synthetic · no camera image/).length).toBe(2);
  });
});

describe("REVIEW FIX 1: command-side HTTP 5xx is an uncertain outcome", () => {
  it("does not report a 5xx as a backend rejection and retries with the SAME command_id", async () => {
    const { ApiError } = await import("./api/client");
    const advanceScenario = vi
      .fn()
      .mockRejectedValueOnce(new ApiError("HTTP_500", "Backend internal error (HTTP 500).", 500))
      .mockResolvedValueOnce(response({ message: "Advance confirmed on retry" }));
    window.location.hash = "#scenarios";
    renderWith(<App />, makeClient(makeSnapshot(), { advanceScenario }));
    const button = await screen.findByRole("button", { name: /Advance \+1000 ms/ });
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(button);

    expect(await screen.findByText(/Command outcome uncertain/)).toBeTruthy();
    expect(screen.queryByText(/Rejected by backend/)).toBeNull();
    const retry = screen.getByRole("button", { name: /Retry same command/ });
    fireEvent.click(retry);
    expect(await screen.findByText(/Advance confirmed on retry/)).toBeTruthy();
    expect(advanceScenario).toHaveBeenCalledTimes(2);
    expect(advanceScenario.mock.calls[1][0].command_id).toBe(advanceScenario.mock.calls[0][0].command_id);
    expect(advanceScenario.mock.calls[1][0]).toEqual(advanceScenario.mock.calls[0][0]);
  });

  it("still reports a structured 409 as a confirmed rejection without a retry", async () => {
    const { ApiError } = await import("./api/client");
    const advanceScenario = vi.fn().mockRejectedValue(new ApiError("STALE_SCENARIO_RUN", "scenario_run_id does not match the active run", 409));
    window.location.hash = "#scenarios";
    renderWith(<App />, makeClient(makeSnapshot(), { advanceScenario }));
    const button = await screen.findByRole("button", { name: /Advance \+1000 ms/ });
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(button);
    expect(await screen.findByText(/Rejected by backend/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Retry same command/ })).toBeNull();
  });
});

describe("REVIEW FIX 2: Black Box replays the selected event's run", () => {
  const OLD_RUN = "33333333-3333-4333-8333-333333333333";
  const telemetry = (seq: number, run: string, altitude: number) =>
    makeEvent(seq, {
      scenario_run_id: run,
      event_type: "TELEMETRY_UPDATED",
      source: "SIMULATOR",
      occurred_at: `2026-01-01T00:00:0${seq % 10}Z`,
      payload: {
        aircraft_id: "AEROGUARD-SIM-001",
        simulation_time: "2026-01-01T00:00:01Z",
        altitude_ft: altitude,
        airspeed_kts: 450,
        heading_deg: 90,
        latitude: 19,
        longitude: 72,
        flight_phase: "CRUISE",
        active_warning_codes: [],
      },
    });
  // Old run: start, telemetry at 30,000 ft, an incident. Current run: start, telemetry at 35,000 ft.
  const events = [
    makeEvent(1, { scenario_run_id: OLD_RUN, event_type: "SCENARIO_STARTED", payload: { scenario_id: "dual_pilot_atc_connected", started_at: "2026-01-01T00:00:00Z" } }),
    telemetry(2, OLD_RUN, 30000),
    makeEvent(3, { scenario_run_id: OLD_RUN, event_type: "GUARDIAN_INCIDENT", source: "GUARDIAN", payload: makeIncident({ scenario_run_id: OLD_RUN }) }),
    makeEvent(4, { scenario_run_id: RUN_ID, event_type: "SCENARIO_STARTED", payload: { scenario_id: "normal_flight", started_at: "2026-01-01T00:00:00Z" } }),
    telemetry(5, RUN_ID, 35000),
  ];
  const client = () =>
    makeClient(makeSnapshot({ latest_event_seq: 5 }), {
      events: (afterSeq: number) => Promise.resolve({ after_seq: afterSeq, events: afterSeq < 5 ? events : [], latest_event_seq: 5, limit: 500 }),
    });

  it("keeps the selected event, replay timeline and aircraft scene on the same (older) run", async () => {
    renderWith(<BlackBoxPage />, client());
    // Default: the current run.
    expect(await screen.findByText(/Event 2 \/ 2/)).toBeTruthy();
    expect(screen.getByTestId("replay-position").textContent).toContain(RUN_ID.slice(0, 8));
    expect(screen.getByText(/FL350/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "All runs" }));
    fireEvent.click(await screen.findByRole("button", { name: "Select event 2" }));

    const position = screen.getByTestId("replay-position").textContent ?? "";
    expect(position).toContain(OLD_RUN.slice(0, 8));
    expect(position).toMatch(/Event 2 \/ 3/); // seq 2 is the 2nd of the old run's 3 events
    expect(screen.getByText(/FL300/)).toBeTruthy(); // old run's aircraft, not the current run's FL350
    expect(screen.queryByText(/FL350/)).toBeNull();
    expect(screen.getByText("Previous run")).toBeTruthy();
    // The old run's milestones (including its incident) drive the rail, not the current run's.
    expect(screen.getByRole("button", { name: /^Incident at/ })).toBeTruthy();

    // Stepping stays inside the old run.
    fireEvent.click(screen.getByRole("button", { name: "Next event" }));
    expect(screen.getByTestId("replay-position").textContent).toMatch(/Event 3 \/ 3/);
    expect(screen.getByTestId("replay-position").textContent).toContain(OLD_RUN.slice(0, 8));

    fireEvent.click(screen.getByRole("button", { name: "Back to current run" }));
    expect(screen.getByTestId("replay-position").textContent).toContain(RUN_ID.slice(0, 8));
    expect(screen.getByText(/FL350/)).toBeTruthy();
    expect(screen.queryByText("Previous run")).toBeNull();
  });
});

describe("Restored real-data displays", () => {
  it("shows the incident history from GET /api/v1/incidents on the Guardian view", async () => {
    const older = makeIncident({ incident_id: "44444444-4444-4444-8444-444444444444", scenario_run_id: "55555555-5555-4555-8555-555555555555" });
    const client = makeClient(makeSnapshot(), { incidents: () => Promise.resolve({ incidents: [older] }) });
    renderWith(<GuardianPage />, client);
    expect(await screen.findByText("Incident history (1)")).toBeTruthy();
    expect(screen.getByText(/44444444 · run 55555555/)).toBeTruthy();
  });

  it("shows telemetry warning codes exactly as reported, or 'None active'", async () => {
    const telemetry = {
      aircraft_id: "AEROGUARD-SIM-001",
      simulation_time: "2026-01-01T00:00:01Z",
      altitude_ft: 35000,
      airspeed_kts: 450,
      heading_deg: 90,
      latitude: 19,
      longitude: 72,
      flight_phase: "CRUISE" as const,
      active_warning_codes: ["SIM_TEST_WARN"],
    };
    renderWith(<FlightDeckPage />, makeClient(makeSnapshot({ telemetry })));
    const box = await screen.findByLabelText("Telemetry warning codes");
    expect(box.textContent).toContain("SIM_TEST_WARN");
    cleanup();
    renderWith(<FlightDeckPage />, makeClient(makeSnapshot({ telemetry: { ...telemetry, active_warning_codes: [] } })));
    expect((await screen.findByLabelText("Telemetry warning codes")).textContent).toContain("None active");
  });

  it("shows the simulated link details separately from backend connectivity", async () => {
    const snapshot = makeSnapshot({ communication: { atc_link_connected: false, last_change_at: "2026-01-01T00:00:05Z", remote_sync_connected: false, pending_sync_count: 3 } });
    renderWith(<SentinelPage />, makeClient(snapshot));
    const details = await screen.findByLabelText("Simulated link details");
    expect(details.textContent).toContain("Disconnected");
    expect(details.textContent).toContain("00:00:05");
    expect(details.textContent).toContain("Not connected");
    expect(details.textContent).toContain("3");
  });
});
