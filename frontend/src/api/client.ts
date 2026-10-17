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

/**
 * Error raised for any failed request.
 *
 * `code` follows the backend's CommonApiError codes (e.g. STALE_SCENARIO_RUN,
 * INCIDENT_MISMATCH) documented in docs/CONTRACTS.md. CommonApiError is not yet
 * exposed in the generated OpenAPI schema, so the body is parsed defensively here
 * rather than with a hand-written interface. `NETWORK_ERROR` means the backend
 * could not be reached at all, so the command may or may not have been applied.
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
    return this.code === "NETWORK_ERROR";
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}) },
    });
  } catch {
    throw new ApiError("NETWORK_ERROR", "Backend unreachable — is the API running on 127.0.0.1:8000?", 0);
  }
  let body: unknown = null;
  const text = await response.text();
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

const post = <T>(path: string, payload: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(payload) });

export const api = {
  health: () => request<HealthResponse>("/healthz"),
  state: () => request<SystemSnapshot>("/api/v1/state"),
  scenarios: () => request<ScenarioListResponse>("/api/v1/scenarios"),
  incidents: () => request<IncidentListResponse>("/api/v1/incidents"),
  events: (afterSeq: number, limit = 500) =>
    request<EventHistoryResponse>(`/api/v1/events?after_seq=${afterSeq}&limit=${limit}`),

  startScenario: (body: ScenarioStartRequest) => post<CommandResponse>("/api/v1/scenarios/start", body),
  advanceScenario: (body: ScenarioAdvanceRequest) => post<CommandResponse>("/api/v1/scenarios/advance", body),
  resetScenario: (body: ScenarioResetRequest) => post<CommandResponse>("/api/v1/scenarios/reset", body),
  acknowledge: (body: PilotAcknowledgement) => post<CommandResponse>("/api/v1/pilots/acknowledge", body),
  atcDecision: (body: ATCDecision) => post<CommandResponse>("/api/v1/atc/decision", body),
  setLink: (body: CommunicationLinkRequest) => post<CommandResponse>("/api/v1/communications/link", body),
};

export type Api = typeof api;

/** Every mutating command carries a fresh UUID so the backend can deduplicate retries. */
export function newCommandId(): string {
  return crypto.randomUUID();
}
