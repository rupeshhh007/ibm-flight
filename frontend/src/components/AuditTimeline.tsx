import { useMemo, useState } from "react";
import { eventLabel } from "../api/events";
import type { EventType, StoredEvent } from "../api/types";
import { formatVirtualTime, shortId } from "./format";
import type { Tone } from "./tones";
import { Empty, Pill } from "./ui";

const TYPE_TONE: Record<EventType, Tone> = {
  SCENARIO_STARTED: "info",
  SCENARIO_ADVANCED: "muted",
  PILOT_OBSERVATION: "muted",
  TELEMETRY_UPDATED: "muted",
  PILOT_ACKNOWLEDGED: "ok",
  ATC_LINK_CHANGED: "info",
  GUARDIAN_INCIDENT: "alert",
  ATC_DECISION: "warn",
  SENTINEL_DECISION: "warn",
  SIMULATOR_ACTION: "ok",
  SCENARIO_RESET: "info",
  SCENARIO_COMPLETED: "info",
};

const NOISY: EventType[] = ["SCENARIO_ADVANCED", "TELEMETRY_UPDATED", "PILOT_OBSERVATION"];

/**
 * Append-only audit history ordered by committed `seq` (never by timestamp).
 * Each row expands to the raw StoredEvent JSON so judges can inspect it.
 */
export function AuditTimeline({ events, currentRunId }: { events: StoredEvent[]; currentRunId: string | null | undefined }) {
  const [scope, setScope] = useState<"run" | "all">("run");
  const [hideNoisy, setHideNoisy] = useState(false);
  const [open, setOpen] = useState<number | null>(null);

  const visible = useMemo(() => {
    let list = scope === "run" ? events.filter((e) => e.scenario_run_id === currentRunId) : events;
    if (hideNoisy) list = list.filter((e) => !NOISY.includes(e.event_type));
    return [...list].reverse();
  }, [events, scope, hideNoisy, currentRunId]);

  return (
    <div className="timeline">
      <div className="timeline__controls" role="group" aria-label="Audit filters">
        <div className="segmented">
          <button type="button" className={scope === "run" ? "is-active" : ""} aria-pressed={scope === "run"} onClick={() => setScope("run")}>
            Current run
          </button>
          <button type="button" className={scope === "all" ? "is-active" : ""} aria-pressed={scope === "all"} onClick={() => setScope("all")}>
            All runs
          </button>
        </div>
        <label className="check">
          <input type="checkbox" checked={hideNoisy} onChange={(e) => setHideNoisy(e.target.checked)} />
          Hide routine ticks
        </label>
        <span className="meta">{visible.length} events</span>
      </div>
      {visible.length === 0 ? (
        <Empty>No events in this view yet.</Empty>
      ) : (
        <ol className="timeline__list">
          {visible.map((event) => (
            <li key={event.seq} className={`timeline__item ${event.scenario_run_id !== currentRunId ? "is-old-run" : ""}`}>
              <button
                type="button"
                className="timeline__row"
                aria-expanded={open === event.seq}
                onClick={() => setOpen(open === event.seq ? null : event.seq)}
              >
                <span className="timeline__seq mono">#{event.seq}</span>
                <Pill tone={TYPE_TONE[event.event_type]}>{eventLabel(event.event_type)}</Pill>
                <span className="meta">{event.source}</span>
                <span className="meta mono timeline__time">{formatVirtualTime(event.occurred_at)}</span>
                <span className="meta mono">run {shortId(event.scenario_run_id)}</span>
              </button>
              {open === event.seq && <pre className="timeline__json">{JSON.stringify(event, null, 2)}</pre>}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
