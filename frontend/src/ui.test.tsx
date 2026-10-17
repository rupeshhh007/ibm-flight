import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Api } from "./api/client";
import type { CommandResponse } from "./api/types";
import { App, SIMULATION_NOTICE } from "./App";
import { AeroGuardProvider, isNewerSnapshot } from "./hooks/useAeroGuard";
import { ATCPage, decisionBlocker } from "./pages/ATCPage";
import { CockpitPage } from "./pages/CockpitPage";
import { SimulationPage } from "./pages/SimulationPage";
import { INCIDENT_ID, RUN_ID, SCENARIOS, makeClient, makeIncident, makeSnapshot } from "./test/fixtures";

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

describe("SimulationPage", () => {
  it("renders every canonical scenario from the API catalogue", async () => {
    renderWith(<SimulationPage />, makeClient(makeSnapshot()));
    for (const s of SCENARIOS) expect((await screen.findAllByText(s.scenario_id)).length).toBeGreaterThan(0);
    expect(screen.queryByText(/missing canonical scenarios/)).toBeNull();
  });

  it("sends Advance with the active run ID and a fresh command ID", async () => {
    const advanceScenario = vi.fn().mockResolvedValue(response({ message: "Advanced virtual time by 1000 ms" }));
    renderWith(<SimulationPage />, makeClient(makeSnapshot(), { advanceScenario }));
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
    renderWith(<SimulationPage />, makeClient(makeSnapshot(), { advanceScenario }));
    const button = await screen.findByRole("button", { name: /Advance \+1000 ms/ });
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(button);
    fireEvent.click(button);
    expect(advanceScenario).toHaveBeenCalledTimes(1);
    await act(async () => resolve(response()));
  });
});

describe("CockpitPage", () => {
  it("acknowledges with alert_id bound to the active incident", async () => {
    const acknowledge = vi.fn().mockResolvedValue(response());
    const snapshot = makeSnapshot({ guardian_state: "AWAITING_ACK", active_incident: makeIncident({ incident_type: "PILOT_RESPONSE_REQUIRED", severity: "WARNING" }) });
    renderWith(<CockpitPage />, makeClient(snapshot, { acknowledge }));
    fireEvent.click(await screen.findByRole("button", { name: "Acknowledge as Pilot 1" }));
    await waitFor(() => expect(acknowledge).toHaveBeenCalledTimes(1));
    expect(acknowledge.mock.calls[0][0]).toMatchObject({ pilot_id: "PILOT_1", alert_id: INCIDENT_ID, scenario_run_id: RUN_ID });
  });

  it("labels missing observations honestly", async () => {
    renderWith(<CockpitPage />, makeClient(makeSnapshot()));
    expect((await screen.findAllByText(/No observation received/)).length).toBe(2);
  });
});

describe("ATCPage", () => {
  it("disables Approve/Reject when Sentinel is not awaiting ATC", async () => {
    renderWith(<ATCPage />, makeClient(makeSnapshot({ active_incident: makeIncident(), sentinel_state: "STANDBY" })));
    const approve = await screen.findByRole("button", { name: /Approve/ });
    expect((approve as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByTestId("decision-blocker").textContent).toMatch(/not awaiting/);
  });

  it("shows success only after the backend confirms, and surfaces rejections", async () => {
    const { ApiError } = await import("./api/client");
    const atcDecision = vi.fn().mockRejectedValue(new ApiError("AUTHORIZATION_REJECTED", "Sentinel rejected", 409));
    const snapshot = makeSnapshot({ active_incident: makeIncident(), sentinel_state: "AWAITING_ATC" });
    renderWith(<ATCPage />, makeClient(snapshot, { atcDecision }));
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
    renderWith(<ATCPage />, makeClient(makeSnapshot({ active_incident: makeIncident(), sentinel_state: "AWAITING_ATC" })));
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
