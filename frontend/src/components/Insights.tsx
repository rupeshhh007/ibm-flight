// Compact derived views: run milestone timeline, ATC communication log,
// observation summary and system status tiles. All inputs are real backend data.
import { useEffect, useRef } from "react";
import type { SystemSnapshot } from "../api/types";
import type { CommsEntry, Milestone, ObservationSummary } from "../hooks/selectors";
import { formatClock, humanize } from "./format";
import { Icon, type IconName } from "./icons";
import { GUARDIAN_TONE, SENTINEL_TONE, type Tone } from "./tones";
import { Empty } from "./ui";

/** Horizontal milestone rail (newest on the right); scrolls sideways for long runs. */
export function RunTimeline({ milestones }: { milestones: Milestone[] }) {
  const railRef = useRef<HTMLDivElement>(null);
  const newest = milestones.length ? milestones[milestones.length - 1].seq : 0;
  // Keep the newest milestone in view as the run progresses.
  useEffect(() => {
    const rail = railRef.current;
    if (rail) rail.scrollLeft = rail.scrollWidth;
  }, [newest]);

  if (milestones.length === 0) return <Empty icon="clock">No milestones yet. Start and advance a scenario.</Empty>;
  return (
    <div className="rail" ref={railRef} tabIndex={0} role="region" aria-label="Run milestones, scrollable">
      <ol className="rail__list">
        {milestones.map((m) => (
          <li key={m.seq} className={`rail__item rail__item--${m.tone}`}>
            <span className="rail__node" aria-hidden="true" />
            <span className="rail__label">{m.label}</span>
            <span className="rail__detail" title={m.detail}>{m.detail}</span>
            <span className="rail__time mono">
              {formatClock(m.at)} · #{m.seq}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** Two-party transcript of authorization events: simulated ATC on the left, aircraft systems on the right. */
export function CommsLog({ entries }: { entries: CommsEntry[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const newest = entries.length ? entries[entries.length - 1].seq : 0;
  // Follow the newest message, like a live transcript.
  useEffect(() => {
    const box = scrollRef.current;
    if (box) box.scrollTop = box.scrollHeight;
  }, [newest]);

  if (entries.length === 0)
    return <Empty icon="tower">No authorization traffic for this run yet. Messages appear when Guardian raises an incident.</Empty>;
  return (
    <div className="comms-scroll" ref={scrollRef} tabIndex={0} role="region" aria-label="Communication log, scrollable">
      <ol className="comms" aria-label="Communication log">
        {entries.map((entry) => (
          <li key={entry.seq} className={`comms__msg comms__msg--${entry.side} comms__msg--${entry.tone}`}>
            <div className="comms__meta">
              <Icon name={entry.side === "atc" ? "tower" : entry.side === "system" ? "link" : "plane"} size={13} />
              <span className="comms__from">{entry.from}</span>
              <span className="comms__time mono">
                {formatClock(entry.at)} · #{entry.seq}
              </span>
            </div>
            <p className="comms__text">{entry.text}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function ObservationSummaryTable({ summary }: { summary: ObservationSummary }) {
  const rows: [string, number, Tone][] = [
    ["Responsive", summary.responsive, "ok"],
    ["Possibly unresponsive", summary.possiblyUnresponsive, "alert"],
    ["Unknown (unusable evidence)", summary.unknown, "muted"],
    ["Camera unavailable", summary.cameraUnavailable, "warn"],
    ["Face not visible", summary.faceNotVisible, "warn"],
  ];
  return (
    <dl className="counts">
      {rows.map(([label, value, tone]) => (
        <div key={label} className="counts__row">
          <dt>
            <span className={`dot dot--${value > 0 ? tone : "muted"}`} aria-hidden="true" />
            {label}
          </dt>
          <dd className="mono">{value}</dd>
        </div>
      ))}
      <div className="counts__row counts__row--total">
        <dt>Total observations (this run)</dt>
        <dd className="mono">{summary.total}</dd>
      </div>
    </dl>
  );
}

function Tile({ icon, title, value, tone, detail }: { icon: IconName; title: string; value: string; tone: Tone; detail: string }) {
  return (
    <div className={`tile tile--${tone}`}>
      <span className="tile__icon" aria-hidden="true">
        <Icon name={icon} size={18} />
      </span>
      <div className="tile__text">
        <span className="tile__title">{title}</span>
        <span className={`tile__value text-${tone}`}>{value}</span>
        <span className="tile__detail">{detail}</span>
      </div>
      <span className={`dot dot--${tone}`} aria-hidden="true" />
    </div>
  );
}

/** Four-up status strip summarising each subsystem from the snapshot. */
export function SystemTiles({ snapshot, observations }: { snapshot: SystemSnapshot; observations: number }) {
  const hasRun = Boolean(snapshot.scenario_run_id);
  const link = snapshot.communication.atc_link_connected;
  return (
    <div className="tiles">
      <Tile icon="shield" title="Guardian" value={humanize(snapshot.guardian_state)} tone={GUARDIAN_TONE[snapshot.guardian_state]} detail={snapshot.active_incident ? "Incident active" : "No active incident"} />
      <Tile icon="radar" title="Sentinel" value={humanize(snapshot.sentinel_state)} tone={SENTINEL_TONE[snapshot.sentinel_state]} detail={`Simulated ATC ${link ? "connected" : "disconnected"}`} />
      <Tile icon="camera" title="Vision" value={`${observations} observations`} tone={observations > 0 ? "info" : "muted"} detail="Pilot observations this run" />
      <Tile icon="plane" title="Simulator" value={snapshot.telemetry ? humanize(snapshot.telemetry.flight_phase) : hasRun ? "Running" : "Idle"} tone={hasRun ? "info" : "muted"} detail={snapshot.last_simulator_action ? `Last action ${snapshot.last_simulator_action.action_type}` : "No action executed"} />
    </div>
  );
}
