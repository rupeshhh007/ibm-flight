import { Fragment, useMemo, useState } from "react";
import { eventLabel } from "../api/events";
import type { EventType, StoredEvent } from "../api/types";
import { formatVirtualTime, shortId } from "./format";
import { Icon } from "./icons";
import { EVENT_TONE } from "./tones";
import { Badge, Empty, Segmented } from "./ui";

const NOISY: EventType[] = ["SCENARIO_ADVANCED", "TELEMETRY_UPDATED", "PILOT_OBSERVATION"];

/**
 * Append-only audit history ordered by committed `seq` (never by timestamp).
 * The table scrolls inside a fixed-height region so long histories never stretch
 * the page; each row expands to the raw StoredEvent JSON for inspection.
 */
export function AuditTimeline({ events, currentRunId }: { events: StoredEvent[]; currentRunId: string | null | undefined }) {
  const [scope, setScope] = useState<"Current run" | "All runs">("Current run");
  const [hideNoisy, setHideNoisy] = useState(false);
  const [open, setOpen] = useState<number | null>(null);

  const visible = useMemo(() => {
    let list = scope === "Current run" ? events.filter((e) => e.scenario_run_id === currentRunId) : events;
    if (hideNoisy) list = list.filter((e) => !NOISY.includes(e.event_type));
    return [...list].reverse();
  }, [events, scope, hideNoisy, currentRunId]);

  return (
    <div className="audit">
      <div className="toolbar" role="group" aria-label="Audit filters">
        <Segmented label="Scope" options={["Current run", "All runs"] as const} value={scope} onChange={setScope} />
        <label className="check">
          <input type="checkbox" checked={hideNoisy} onChange={(e) => setHideNoisy(e.target.checked)} />
          Hide routine ticks
        </label>
        <span className="toolbar__spacer" />
        <span className="muted-text">{visible.length} events</span>
      </div>
      {visible.length === 0 ? (
        <Empty icon="list">No events in this view yet.</Empty>
      ) : (
        <div className="table-wrap table-wrap--scroll table-wrap--tall" tabIndex={0} role="region" aria-label="Audit events, scrollable">
          <table className="table table--interactive">
            <thead>
              <tr>
                <th scope="col" className="num">Seq</th>
                <th scope="col">Event</th>
                <th scope="col">Source</th>
                <th scope="col">Virtual time</th>
                <th scope="col">Run</th>
                <th scope="col">
                  <span className="sr-only">Expand</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {visible.map((event) => {
                const expanded = open === event.seq;
                return (
                  <Fragment key={event.seq}>
                    <tr className={event.scenario_run_id !== currentRunId ? "is-dim" : ""}>
                      <td className="mono num muted-text">#{event.seq}</td>
                      <td>
                        <Badge tone={EVENT_TONE[event.event_type]}>{eventLabel(event.event_type)}</Badge>
                      </td>
                      <td className="muted-text">{event.source}</td>
                      <td className="mono">{formatVirtualTime(event.occurred_at)}</td>
                      <td className="mono muted-text">{shortId(event.scenario_run_id)}</td>
                      <td className="cell-action">
                        <button
                          type="button"
                          className="icon-btn"
                          aria-expanded={expanded}
                          aria-label={`${expanded ? "Hide" : "Show"} raw JSON for event ${event.seq}`}
                          onClick={() => setOpen(expanded ? null : event.seq)}
                        >
                          <Icon name="chevron" size={14} className={expanded ? "rot-90" : ""} />
                        </button>
                      </td>
                    </tr>
                    {expanded && (
                      <tr className="json-row">
                        <td colSpan={6}>
                          <pre className="json">{JSON.stringify(event, null, 2)}</pre>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
