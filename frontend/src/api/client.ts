// Typed REST client for the AeroGuard simulation API.
// Every path is relative ("/api/v1/..."): in development Vite proxies it to the
// local backend, so no deployment address is baked into the bundle.
import type {
  ATCDecision,
  CommandResponse,
  CommunicationLinkRequest,
  EventHistoryResponse,
  HealthResponse,
  IncidentListResponse,
  PilotAcknowledgement,
  ScenarioAdvanceRequest,
  ScenarioListResponse,
  ScenarioResetRequest,
  ScenarioStartRequest,
  SystemSnapshot,
} from "./types";

export const DEFAULT_REQUEST_TIMEOUT_MS = 10_000;

export interface RequestOptions extends RequestInit {
  timeoutMs?: number;
}

/**
 * Error raised for any failed request.
 *
 * `code` follows the backend's CommonApiError codes (e.g. STALE_SCENARIO_RUN,
 * INCIDENT_MISMATCH) documented in docs/CONTRACTS.md. CommonApiError is not yet
 * exposed in the generated OpenAPI schema, so the body is parsed defensively here
 * rather than with a hand-written interface. `NETWORK_ERROR`, `TIMEOUT_ERROR`,
 * and `UNCERTAIN_TRANSPORT_ERROR` mean transport failed or timed out, so the
 * command outcome is uncertain (it may or may not have been applied by the backend).
 */
export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
    readonly details: string[] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }

  get isNetworkError(): boolean {
    return (
      this.code === "NETWORK_ERROR" ||
      this.code === "TIMEOUT_ERROR" ||
      this.code === "UNCERTAIN_TRANSPORT_ERROR"
    );
  }

  get isTimeout(): boolean {
    return this.code === "TIMEOUT_ERROR";
  }

  get isUncertain(): boolean {
    return (
      this.code === "NETWORK_ERROR" ||
      this.code === "TIMEOUT_ERROR" ||
      this.code === "UNCERTAIN_TRANSPORT_ERROR"
    );
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function parseErrorBody(status: number, body: unknown): ApiError {
  if (isRecord(body) && typeof body.code === "string" && typeof body.message === "string") {
    const details = Array.isArray(body.details) ? body.details.filter((d): d is string => typeof d === "string") : [];
    return new ApiError(body.code, body.message, status, details);
  }
  if (isRecord(body) && typeof body.detail === "string") {
    return new ApiError(`HTTP_${status}`, body.detail, status);
  }
  return new ApiError(`HTTP_${status}`, `Request failed with HTTP ${status}`, status);
}

async function request<T>(path: string, init?: RequestOptions): Promise<T> {
  const timeoutMs = init?.timeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS;
  const controller = new AbortController();
  let timedOut = false;
  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  const signal = controller.signal;
  if (init?.signal) {
    if (init.signal.aborted) {
      clearTimeout(timeoutId);
      controller.abort();
    } else {
      init.signal.addEventListener("abort", () => {
        clearTimeout(timeoutId);
        controller.abort();
      });
    }
  }

  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      signal,
      headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}) },
    });
  } catch {
    clearTimeout(timeoutId);
    if (timedOut) {
      throw new ApiError(
        "TIMEOUT_ERROR",
        `Request timed out after ${timeoutMs}ms — backend status uncertain`,
        0,
      );
    }
    throw new ApiError("NETWORK_ERROR", "Backend unreachable — is the API running on 127.0.0.1:8000?", 0);
  }

  let text: string;
  try {
    text = await response.text();
  } catch {
    clearTimeout(timeoutId);
    if (timedOut) {
      throw new ApiError(
        "TIMEOUT_ERROR",
        `Request timed out reading response after ${timeoutMs}ms — backend status uncertain`,
        response.status || 0,
      );
    }
    throw new ApiError(
      "UNCERTAIN_TRANSPORT_ERROR",
      "Connection failed while reading response body — command may have executed",
      response.status || 0,
    );
  } finally {
    clearTimeout(timeoutId);
  }

  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!response.ok) throw parseErrorBody(response.status, body);
  return body as T;
}

const post = <T>(path: string, payload: unknown, options?: RequestOptions) =>
  request<T>(path, { ...options, method: "POST", body: JSON.stringify(payload) });

export const api = {
  health: (opts?: RequestOptions) => request<HealthResponse>("/healthz", opts),
  state: (opts?: RequestOptions) => request<SystemSnapshot>("/api/v1/state", opts),
  scenarios: (opts?: RequestOptions) => request<ScenarioListResponse>("/api/v1/scenarios", opts),
  incidents: (opts?: RequestOptions) => request<IncidentListResponse>("/api/v1/incidents", opts),
  events: (afterSeq: number, limit = 500, opts?: RequestOptions) =>
    request<EventHistoryResponse>(`/api/v1/events?after_seq=${afterSeq}&limit=${limit}`, opts),

  startScenario: (body: ScenarioStartRequest, opts?: RequestOptions) =>
    post<CommandResponse>("/api/v1/scenarios/start", body, opts),
  advanceScenario: (body: ScenarioAdvanceRequest, opts?: RequestOptions) =>
    post<CommandResponse>("/api/v1/scenarios/advance", body, opts),
  resetScenario: (body: ScenarioResetRequest, opts?: RequestOptions) =>
    post<CommandResponse>("/api/v1/scenarios/reset", body, opts),
  acknowledge: (body: PilotAcknowledgement, opts?: RequestOptions) =>
    post<CommandResponse>("/api/v1/pilots/acknowledge", body, opts),
  atcDecision: (body: ATCDecision, opts?: RequestOptions) =>
    post<CommandResponse>("/api/v1/atc/decision", body, opts),
  setLink: (body: CommunicationLinkRequest, opts?: RequestOptions) =>
    post<CommandResponse>("/api/v1/communications/link", body, opts),
};

export type Api = typeof api;

/** Every mutating command carries a fresh UUID so the backend can deduplicate retries. */
export function newCommandId(): string {
  return crypto.randomUUID();
}
