import { useEffect, useMemo, useState } from "react";
import { CANONICAL_SCENARIO_IDS } from "../api/types";
import { AuditTimeline } from "../components/AuditTimeline";
import { Card, Chip, flightStatus, ScenarioArt, SectionHeader } from "../components/console";
import { formatClock, shortId } from "../components/format";
import { Icon } from "../components/icons";
import { RunTimeline } from "../components/Insights";
import { Empty, Notice, Segmented, Switch } from "../components/ui";
import { eventsForRun, runMilestones } from "../hooks/selectors";
import { useAeroGuard } from "../hooks/useAeroGuard";

const ADVANCE_STEPS_MS = [500, 1000, 2000, 5000] as const;
type AdvanceStep = (typeof ADVANCE_STEPS_MS)[number];

export function ScenariosPage() {
  const { snapshot, scenarios, events, pending, commands } = useAeroGuard();
  const [selected, setSelected] = useState<string | null>(null);
  const [deltaMs, setDeltaMs] = useState<AdvanceStep>(1000);

  // Default the picker to the active scenario (or the first one) once data arrives.
  useEffect(() => {
    if (selected === null && scenarios && scenarios.length > 0) {
      setSelected(snapshot?.scenario_id ?? scenarios[0].scenario_id);
    }
  }, [selected, scenarios, snapshot?.scenario_id]);

  const runEvents = useMemo(() => eventsForRun(events, snapshot?.scenario_run_id), [events, snapshot?.scenario_run_id]);
  const milestones = useMemo(() => runMilestones(runEvents), [runEvents]);
  const missing = scenarios ? CANONICAL_SCENARIO_IDS.filter((id) => !scenarios.some((s) => s.scenario_id === id)) : [];
  const hasRun = Boolean(snapshot?.scenario_run_id);
  const busy = pending !== null;
  const linkConnected = snapshot?.communication.atc_link_connected ?? false;
  const status = flightStatus(snapshot);

  return (
    <div className="view">
      <SectionHeader
        title="Scenario simulation"
        subtitle="Deterministic synthetic emergency situations from GET /api/v1/scenarios"
        actions={
          <button type="button" className="btn btn--primary btn--lg" disabled={busy || !selected} onClick={() => selected && commands.start(selected)}>
            <Icon name="play" size={14} />
            {hasRun ? "Start selected scenario (new run)" : "Start selected scenario"}
            <Icon name="chevron" size={12} />
          </button>
        }
      />

      {scenarios === null ? (
        <Empty>Loading scenario catalogue…</Empty>
      ) : (
        <div className="tiles5" role="radiogroup" aria-label="Scenario">
          {scenarios.map((s, i) => {
            const isActive = snapshot?.scenario_id === s.scenario_id && hasRun;
            return (
              <label key={s.scenario_id} className={`stile5 ${selected === s.scenario_id ? "is-selected" : ""}`}>
                <input type="radio" name="scenario" value={s.scenario_id} checked={selected === s.scenario_id} onChange={() => setSelected(s.scenario_id)} />
                <span className="stile5__head">
                  <span className="stile5__num" aria-hidden="true">
                    {i + 1}
                  </span>
                  <span className="stile5__name">{s.name}</span>
                </span>
                <span className="stile5__desc">{s.description}</span>
                <ScenarioArt id={s.scenario_id} />
                <span className="stile5__meta">
                  <span className="mono">{s.scenario_id}</span>
                  {isActive && <Chip tone="info">Active run</Chip>}
                </span>
                <span className="stile5__expect">Expected: {s.p0_behavior}</span>
              </label>
            );
          })}
        </div>
      )}
      {missing.length > 0 && <Notice tone="warn" title="Backend catalogue is missing canonical scenarios:">{missing.join(", ")}</Notice>}

      <section className="runbar" aria-label="Run controls">
        <div className="runbar__id">
          <span className="runbar__label">Scenario progress</span>
          <strong className="mono">{snapshot?.scenario_id ?? "No active scenario"}</strong>
          <span className="mono runbar__meta">
            Run {shortId(snapshot?.scenario_run_id)} · T {formatClock(snapshot?.virtual_time)} · seq {snapshot?.latest_event_seq ?? "—"}
          </span>
        </div>
        <div className="runbar__progress">
          <div className="runbar__ticks" aria-hidden="true">
            {milestones.slice(-24).map((m) => (
              <span key={m.seq} className={`runbar__tick runbar__tick--${m.tone}`} />
            ))}
          </div>
          <span className="runbar__meta">
            {runEvents.length} events · {milestones.length} milestones <Chip tone={status.tone}>{status.label}</Chip>
          </span>
        </div>
        <div className="runbar__controls">
          <Segmented label="Advance step" options={ADVANCE_STEPS_MS} value={deltaMs} onChange={setDeltaMs} format={(ms) => (ms >= 1000 ? `${ms / 1000}s` : `${ms}ms`)} />
          <button type="button" className="btn btn--secondary" disabled={busy || !hasRun} onClick={() => commands.advance(deltaMs)}>
            <Icon name="forward" size={14} />
            Advance +{deltaMs} ms
          </button>
          <button type="button" className="btn btn--ghost" disabled={busy || !hasRun} onClick={() => commands.reset()}>
            <Icon name="reset" size={14} />
            Reset run
          </button>
        </div>
        <div className="runbar__link">
          <span className="runbar__label">Simulated ATC link</span>
          <div className="runbar__switch">
            <span className={linkConnected ? "text-ok" : "text-alert"}>{linkConnected ? "Connected" : "Disconnected"}</span>
            <Switch label="Simulated ATC link connected" checked={linkConnected} disabled={busy || !hasRun} onChange={(next) => commands.setLink(next)} />
          </div>
          <span className="hint">Disconnecting alone never authorizes an action.</span>
        </div>
      </section>
      {snapshot && <p className="status-line">Backend status: {snapshot.status_text}</p>}

      <Card title={`Run timeline (${milestones.length})`} icon="clock">
        <RunTimeline milestones={milestones} />
      </Card>

      <Card title="Run event log" icon="list">
        <AuditTimeline events={events} currentRunId={snapshot?.scenario_run_id} />
      </Card>
    </div>
  );
}
