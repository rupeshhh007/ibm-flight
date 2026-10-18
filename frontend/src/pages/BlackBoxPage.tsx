import { useEffect, useMemo, useState } from "react";
import { eventLabel } from "../api/events";
import { isEventOfType, type EventType, type StoredEvent } from "../api/types";
import { Card, Chip, SectionHeader } from "../components/console";
import { formatClock, formatVirtualTime, humanize, shortId } from "../components/format";
import { Icon } from "../components/icons";
import { FlightScene } from "../components/scene/FlightScene";
import { EVENT_TONE } from "../components/tones";
import { Empty, Segmented } from "../components/ui";
import { eventsForRun, incidentEventTime, runMilestones, sceneSamples } from "../hooks/selectors";
import { useAeroGuard } from "../hooks/useAeroGuard";

const SPEEDS = ["1x", "2x", "4x"] as const;
type Speed = (typeof SPEEDS)[number];
const STEP_MS: Record<Speed, number> = { "1x": 900, "2x": 450, "4x": 220 };

/**
 * Event-based reconstruction of a run. There is no video: "play" simply steps the
 * selection through the committed events in sequence order.
 */
export function BlackBoxPage() {
  const { snapshot, events } = useAeroGuard();
  const runId = snapshot?.scenario_run_id;
  const runEvents = useMemo(() => eventsForRun(events, runId), [events, runId]);
  const [scope, setScope] = useState<"Current run" | "All runs">("Current run");
  const [query, setQuery] = useState("");
  const [type, setType] = useState<EventType | "ALL">("ALL");
  const [selectedSeq, setSelectedSeq] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<Speed>("1x");

  // Everything on the stage (transport, position, scene, incident zone, milestones) refers to ONE run:
  // the run of the selected event, or the current run when nothing is selected. Selecting an older
  // run's event under "All runs" therefore replays that run, never the current one.
  const selectedEvent: StoredEvent | null = selectedSeq === null ? null : events.find((e) => e.seq === selectedSeq) ?? null;
  const replayRunId = selectedEvent?.scenario_run_id ?? runId ?? null;
  const replay = useMemo(() => eventsForRun(events, replayRunId), [events, replayRunId]); // commit order
  const selected: StoredEvent | null = selectedEvent ?? replay[replay.length - 1] ?? null;
  const index = selected ? replay.findIndex((e) => e.seq === selected.seq) : -1;
  const historical = replayRunId !== null && replayRunId !== (runId ?? null);

  // A new run resets the replay cursor.
  useEffect(() => {
    setSelectedSeq(null);
    setPlaying(false);
  }, [runId]);

  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => {
      setSelectedSeq((cur) => {
        const i = cur === null ? -1 : replay.findIndex((e) => e.seq === cur);
        if (i + 1 >= replay.length) {
          setPlaying(false);
          return cur;
        }
        return replay[i + 1].seq;
      });
    }, STEP_MS[speed]);
    return () => clearInterval(timer);
  }, [playing, speed, replay]);

  const samples = useMemo(() => sceneSamples(replay), [replay]);
  const incidentId = useMemo(() => {
    const hit = replay.find((e) => isEventOfType(e, "GUARDIAN_INCIDENT"));
    return hit && isEventOfType(hit, "GUARDIAN_INCIDENT") ? hit.payload.incident_id : null;
  }, [replay]);
  const incidentAt = useMemo(() => incidentEventTime(replay, incidentId), [replay, incidentId]);
  const milestones = useMemo(() => runMilestones(replay), [replay]);

  // Reconstruct the replay run's scene at the selected event: aircraft at the last telemetry sample
  // at/before it, incident zone only once that run's incident had been committed.
  const cursorSeq = selected ? selected.seq : Infinity;
  let focusIndex: number | null = null;
  replay.forEach((e) => {
    if (isEventOfType(e, "TELEMETRY_UPDATED") && e.seq <= cursorSeq) focusIndex = samples.findIndex((s) => s.telemetry === e.payload);
  });
  const incidentVisible = incidentAt !== null && replay.some((e) => isEventOfType(e, "GUARDIAN_INCIDENT") && e.seq <= cursorSeq);

  const list = useMemo(() => {
    const q = query.trim().toLowerCase();
    let l = scope === "Current run" ? runEvents : events;
    if (type !== "ALL") l = l.filter((e) => e.event_type === type);
    if (q) l = l.filter((e) => `${e.seq} ${eventLabel(e.event_type)} ${e.source} ${e.event_type}`.toLowerCase().includes(q));
    return [...l].reverse();
  }, [events, runEvents, scope, type, query]);

  const types = useMemo(() => Array.from(new Set(events.map((e) => e.event_type))).sort(), [events]);
  const step = (delta: number) => {
    setPlaying(false);
    if (replay.length === 0) return;
    const i = Math.min(Math.max((index < 0 ? replay.length - 1 : index) + delta, 0), replay.length - 1);
    setSelectedSeq(replay[i].seq);
  };

  return (
    <div className="view">
      <SectionHeader title="Black box replay" subtitle="Event timeline & visual reconstruction from committed audit events · no video is recorded" />

      <section className="bb-stage" aria-label="Replay">
        <div className="bb-stage__controls">
          <div className="bb-transport" role="group" aria-label="Replay controls">
            <button type="button" className="icon-btn icon-btn--lg" onClick={() => step(-1)} disabled={replay.length === 0} aria-label="Previous event">
              <Icon name="skipBack" size={16} />
            </button>
            <button
              type="button"
              className="icon-btn icon-btn--play"
              onClick={() => {
                if (!playing && index >= replay.length - 1 && replay.length) setSelectedSeq(replay[0].seq);
                setPlaying((p) => !p);
              }}
              disabled={replay.length === 0}
              aria-label={playing ? "Pause replay" : "Play replay"}
            >
              <Icon name={playing ? "pause" : "play"} size={18} />
            </button>
            <button type="button" className="icon-btn icon-btn--lg" onClick={() => step(1)} disabled={replay.length === 0} aria-label="Next event">
              <Icon name="skipFwd" size={16} />
            </button>
            <Segmented label="Replay speed" options={SPEEDS} value={speed} onChange={setSpeed} />
          </div>
          <div className="bb-position mono" data-testid="replay-position">
            {replay.length ? `Event ${Math.max(index, 0) + 1} / ${replay.length}` : "No events"} · {selected ? formatClock(selected.occurred_at) : "—"} · run{" "}
            {shortId(replayRunId)}
          </div>
          {historical && (
            <div className="bb-historical" role="status">
              <Chip tone="warn">Previous run</Chip>
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => { setPlaying(false); setSelectedSeq(null); }}>
                Back to current run
              </button>
            </div>
          )}
          <div className="bb-progress" aria-hidden="true">
            <span style={{ width: replay.length ? `${((Math.max(index, 0) + 1) / replay.length) * 100}%` : "0%" }} />
          </div>
        </div>
        <div className="bb-stage__scene">
          <FlightScene key={replayRunId ?? "none"} samples={samples} incidentAt={incidentVisible ? incidentAt : null} incidentLabel="Guardian incident" emergency={incidentVisible} focusIndex={focusIndex} callsignVisible crop="band" />
          {selected && (
            <div className="bb-callout">
              <span className="mono">{formatClock(selected.occurred_at)}</span>
              <strong>{eventLabel(selected.event_type)}</strong>
            </div>
          )}
        </div>
        <ol className="bb-rail" aria-label="Milestones">
          {milestones.length === 0 && <li className="bb-rail__empty">No milestones yet — start and advance a scenario.</li>}
          {milestones.map((m) => (
            <li key={m.seq} className={`bb-rail__item bb-rail__item--${m.tone} ${selected?.seq === m.seq ? "is-current" : ""} ${m.seq <= cursorSeq ? "is-past" : ""}`}>
              <button type="button" onClick={() => { setPlaying(false); setSelectedSeq(m.seq); }} aria-label={`${m.label} at ${formatClock(m.at)}`}>
                <span className="bb-rail__node" aria-hidden="true" />
                <span className="bb-rail__label">{m.label}</span>
                <span className="bb-rail__time mono">{formatClock(m.at)}</span>
              </button>
            </li>
          ))}
        </ol>
      </section>

      <div className="g75">
        <Card title="Event timeline" icon="list" flush>
          <div className="toolbar toolbar--padded" role="group" aria-label="Event filters">
            <Segmented label="Scope" options={["Current run", "All runs"] as const} value={scope} onChange={setScope} />
            <label className="search">
              <Icon name="search" size={14} />
              <input className="input input--bare" placeholder="Filter by type, source or seq" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Filter events" />
            </label>
            <select className="input input--sm" value={type} onChange={(e) => setType(e.target.value as EventType | "ALL")} aria-label="Event type">
              <option value="ALL">All types</option>
              {types.map((t) => (
                <option key={t} value={t}>
                  {eventLabel(t)}
                </option>
              ))}
            </select>
            <span className="muted-text">{list.length} events</span>
          </div>
          {list.length === 0 ? (
            <Empty icon="list">No events match this view.</Empty>
          ) : (
            <div className="table-wrap table-wrap--scroll table-wrap--tall" tabIndex={0} role="region" aria-label="Events, scrollable">
              <table className="table table--interactive">
                <thead>
                  <tr>
                    <th scope="col" className="num">Seq</th>
                    <th scope="col">Event</th>
                    <th scope="col">Source</th>
                    <th scope="col">Virtual time</th>
                    <th scope="col">Run</th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((e) => (
                    <tr
                      key={e.seq}
                      className={`${selected?.seq === e.seq ? "is-active" : ""} ${e.scenario_run_id !== runId ? "is-dim" : ""}`}
                      onClick={() => { setPlaying(false); setSelectedSeq(e.seq); }}
                    >
                      <td className="mono num muted-text">
                        <button type="button" className="row-btn" onClick={() => { setPlaying(false); setSelectedSeq(e.seq); }} aria-label={`Select event ${e.seq}`}>
                          {e.seq}
                        </button>
                      </td>
                      <td>
                        <Chip tone={EVENT_TONE[e.event_type]}>{eventLabel(e.event_type)}</Chip>
                      </td>
                      <td className="muted-text">{e.source}</td>
                      <td className="mono">{formatVirtualTime(e.occurred_at)}</td>
                      <td className="mono muted-text">{shortId(e.scenario_run_id)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="Selected event" icon="blackbox">
          {selected ? (
            <div className="evdetail">
              <div className="evdetail__head">
                <Chip tone={EVENT_TONE[selected.event_type]}>{eventLabel(selected.event_type)}</Chip>
                <span className="mono muted-text">seq {selected.seq}</span>
              </div>
              <dl className="mini-grid">
                <div>
                  <dt>Virtual time</dt>
                  <dd className="mono">{formatVirtualTime(selected.occurred_at)}</dd>
                </div>
                <div>
                  <dt>Source</dt>
                  <dd>{humanize(selected.source)}</dd>
                </div>
                <div>
                  <dt>Run</dt>
                  <dd className="mono">{shortId(selected.scenario_run_id)}</dd>
                </div>
                <div>
                  <dt>Event ID</dt>
                  <dd className="mono">{shortId(selected.event_id)}</dd>
                </div>
              </dl>
              <pre className="json" tabIndex={0} aria-label="Raw event JSON">{JSON.stringify(selected, null, 2)}</pre>
            </div>
          ) : (
            <Empty icon="blackbox">No events recorded yet.</Empty>
          )}
        </Card>
      </div>
    </div>
  );
}
