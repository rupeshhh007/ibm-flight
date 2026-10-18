import { afterEach, describe, expect, it, vi } from "vitest";
import { makeEvent } from "../test/fixtures";
import { api, ApiError, parseErrorBody } from "./client";
import { MAX_EVENTS, eventLabel, latestSeq, mergeEvents } from "./events";

describe("mergeEvents", () => {
  it("orders by seq and drops duplicates from overlapping pages", () => {
    const merged = mergeEvents([makeEvent(1), makeEvent(2)], [makeEvent(3), makeEvent(2), makeEvent(3)]);
    expect(merged.map((e) => e.seq)).toEqual([1, 2, 3]);
  });

  it("re-sorts out-of-order arrivals", () => {
    expect(mergeEvents([makeEvent(5)], [makeEvent(3), makeEvent(4)]).map((e) => e.seq)).toEqual([3, 4, 5]);
  });

  it("returns the same array when nothing is new (no needless re-render)", () => {
    const current = [makeEvent(1)];
    expect(mergeEvents(current, [makeEvent(1)])).toBe(current);
  });

  it("caps memory at MAX_EVENTS, keeping the newest", () => {
    const many = Array.from({ length: MAX_EVENTS + 10 }, (_, i) => makeEvent(i + 1));
    const merged = mergeEvents([], many);
    expect(merged).toHaveLength(MAX_EVENTS);
    expect(latestSeq(merged)).toBe(MAX_EVENTS + 10);
  });

  it("labels event types readably", () => {
    expect(eventLabel("ATC_LINK_CHANGED")).toBe("ATC Link Changed");
  });
});

describe("parseErrorBody", () => {
  it("reads the backend CommonApiError shape", () => {
    const error = parseErrorBody(409, { code: "STALE_SCENARIO_RUN", message: "stale", details: ["a", 3] });
    expect(error).toMatchObject({ code: "STALE_SCENARIO_RUN", message: "stale", status: 409, details: ["a"] });
  });

  it("falls back for unknown bodies", () => {
    expect(parseErrorBody(500, "boom").code).toBe("HTTP_500");
  });
});

describe("5xx parsing", () => {
  it("keeps plain-text 5xx errors neutral (the shared client cannot know whether a command was involved)", () => {
    const error = parseErrorBody(500, "Internal Server Error");
    expect(error.message).toBe("Backend internal error (HTTP 500).");
    expect(error.code).toBe("HTTP_500");
  });
});

describe("api client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("POSTs typed JSON to the relative contract path", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const body = { command_id: "c", scenario_run_id: "r", delta_ms: 1000 };
    await api.advanceScenario(body);
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/v1/scenarios/advance");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual(body);
  });

  it("builds the bounded event-history query", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.events(42);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/events?after_seq=42&limit=500");
  });

  it("raises ApiError with the backend code on 409", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ code: "INCIDENT_MISMATCH", message: "no", details: [] }), { status: 409 })),
    );
    await expect(api.state()).rejects.toMatchObject({ code: "INCIDENT_MISMATCH", status: 409 });
  });

  it("maps an unreachable backend to NETWORK_ERROR", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const error = await api.state().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).isNetworkError).toBe(true);
    expect((error as ApiError).isUncertain).toBe(true);
  });

  it("times out stalled requests after timeoutMs and raises TIMEOUT_ERROR", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(
        (_path, init?: RequestInit) =>
          new Promise((_, reject) => {
            if (init?.signal) {
              init.signal.addEventListener("abort", () => {
                reject(new DOMException("The user aborted a request.", "AbortError"));
              });
            }
          }),
      ),
    );
    const error = await api.state({ timeoutMs: 30 }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("TIMEOUT_ERROR");
    expect((error as ApiError).isTimeout).toBe(true);
    expect((error as ApiError).isUncertain).toBe(true);
  });

  it("classifies response-body streaming failure as UNCERTAIN_TRANSPORT_ERROR", async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      text: () => Promise.reject(new Error("Connection reset by peer while streaming response")),
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse));
    const error = await api.state().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("UNCERTAIN_TRANSPORT_ERROR");
    expect((error as ApiError).isUncertain).toBe(true);
  });

  it("distinguishes confirmed backend rejections from transport errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ code: "AUTHORIZATION_REJECTED", message: "Rejected by Sentinel", details: ["pilot responsive"] }),
          { status: 409 },
        ),
      ),
    );
    const error = await api.state().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("AUTHORIZATION_REJECTED");
    expect((error as ApiError).isUncertain).toBe(false);
    expect((error as ApiError).status).toBe(409);
  });
});
