import { useEffect, useMemo, useState } from "react";
import { CANONICAL_SCENARIO_IDS } from "../api/types";
import { AuditTimeline } from "../components/AuditTimeline";
import { FlightDisplay } from "../components/FlightDisplay";
import { formatVirtualTime, shortId } from "../components/format";
import { SentinelPanel } from "../components/StatePanels";
import { Empty, Field, Panel, Pill } from "../components/ui";
import { eventsForRun, sentinelDecisions, telemetryTrack } from "../hooks/selectors";
import { useAeroGuard } from "../hooks/useAeroGuard";

const ADVANCE_STEPS_MS = [500, 1000, 2000, 5000];

export function SimulationPage() {
  const { snapshot, scenarios, events, pending, commands } = useAeroGuard();
  const [selected, setSelected] = useState<string | null>(null);
  const [deltaMs, setDeltaMs] = useState(1000);

  // Default the picker to the active scenario (or the first one) once data arrives.
  useEffect(() => {
    if (selected === null && scenarios && scenarios.length > 0) {
      setSelected(snapshot?.scenario_id ?? scenarios[0].scenario_id);
    }
  }, [selected, scenarios, snapshot?.scenario_id]);

  const runEvents = useMemo(() => eventsForRun(events, snapshot?.scenario_run_id), [events, snapshot?.scenario_run_id]);
  const track = useMemo(() => telemetryTrack(runEvents), [runEvents]);
  const decisions = useMemo(() => sentinelDecisions(runEvents), [runEvents]);

  const missing = scenarios ? CANONICAL_SCENARIO_IDS.filter((id) => !scenarios.some((s) => s.scenario_id === id)) : [];
  const hasRun = Boolean(snapshot?.scenario_run_id);
  const busy = pending !== null;

  return (
    <div className="grid grid--sim">
      <Panel title="Scenario" subtitle="Deterministic synthetic scenarios from GET /api/v1/scenarios" className="area-scenarios">
        {scenarios === null ? (
          <Empty>Loading scenario catalogue…</Empty>
        ) : (
          <>
            <div className="scenarios" role="radiogroup" aria-label="Scenario">
              {scenarios.map((s) => (
                <label key={s.scenario_id} className={`scenario ${selected === s.scenario_id ? "is-selected" : ""}`}>
                  <input
                    type="radio"
                    name="scenario"
                    value={s.scenario_id}
                    checked={selected === s.scenario_id}
                    onChange={() => setSelected(s.scenario_id)}
                  />
                  <span className="scenario__name">
                    {s.name}
                    {snapshot?.scenario_id === s.scenario_id && hasRun && <Pill tone="info">Active</Pill>}
                  </span>
                  <span className="scenario__id mono">{s.scenario_id}</span>
                  <span className="scenario__desc">{s.description}</span>
                  <span className="scenario__behavior">Expected: {s.p0_behavior}</span>
                </label>
              ))}
            </div>
            {missing.length > 0 && <p className="text-warn">Backend catalogue is missing canonical scenarios: {missing.join(", ")}</p>}
          </>
        )}
      </Panel>

      <Panel title="Run controls" className="area-controls">
        <dl className="fields fields--2">
          <Field label="Active scenario" mono>
            {snapshot?.scenario_id ?? "—"}
          </Field>
          <Field label="Run ID" mono>
            <span title={snapshot?.scenario_run_id ?? undefined}>{shortId(snapshot?.scenario_run_id)}</span>
          </Field>
          <Field label="Virtual time" mono>
            {formatVirtualTime(snapshot?.virtual_time)}
          </Field>
          <Field label="Latest event seq" mono>
            {snapshot?.latest_event_seq ?? "—"}
          </Field>
        </dl>
        {snapshot && <p className="status-text">{snapshot.status_text}</p>}

        <div className="control-block">
          <button
            type="button"
            className="btn btn--primary btn--wide"
            disabled={busy || !selected}
            onClick={() => selected && commands.start(selected)}
          >
            {hasRun ? "Start selected scenario (new run)" : "Start selected scenario"}
          </button>
        </div>

        <div className="control-block">
          <span className="field__label" id="advance-label">
            Advance virtual time
          </span>
          <div className="segmented" role="group" aria-labelledby="advance-label">
            {ADVANCE_STEPS_MS.map((ms) => (
              <button key={ms} type="button" className={deltaMs === ms ? "is-active" : ""} aria-pressed={deltaMs === ms} onClick={() => setDeltaMs(ms)}>
                {ms >= 1000 ? `${ms / 1000}s` : `${ms}ms`}
              </button>
            ))}
          </div>
          <div className="btn-row">
            <button type="button" className="btn" disabled={busy || !hasRun} onClick={() => commands.advance(deltaMs)}>
              Advance +{deltaMs} ms
            </button>
            <button type="button" className="btn btn--ghost" disabled={busy || !hasRun} onClick={() => commands.reset()}>
              Reset run
            </button>
          </div>
        </div>

        <div className="control-block">
          <span className="field__label">Simulated ATC link (scenario input)</span>
          <div className="btn-row">
            <button
              type="button"
              className="btn btn--small"
              disabled={busy || !hasRun || snapshot?.communication.atc_link_connected === true}
              onClick={() => commands.setLink(true)}
            >
              Connect
            </button>
            <button
              type="button"
              className="btn btn--small btn--ghost"
              disabled={busy || !hasRun || snapshot?.communication.atc_link_connected === false}
              onClick={() => commands.setLink(false)}
            >
              Disconnect
            </button>
            <Pill tone={snapshot?.communication.atc_link_connected ? "ok" : "alert"}>
              {snapshot?.communication.atc_link_connected ? "Connected" : "Disconnected"}
            </Pill>
          </div>
          <p className="meta">Disconnecting alone never authorizes an action.</p>
        </div>
      </Panel>

      <Panel title="Flight display" subtitle="Synthetic 2D track for the current run" className="area-flight">
        <FlightDisplay track={track} actionLabel={snapshot?.last_simulator_action?.action_type ?? null} />
      </Panel>

      <div className="area-sentinel">
        {snapshot ? (
          <SentinelPanel state={snapshot.sentinel_state} decisions={decisions} lastAction={snapshot.last_simulator_action} />
        ) : (
          <Empty>Loading…</Empty>
        )}
      </div>

      <Panel title="Audit event history" subtitle="Ordered by committed sequence number · click a row for raw JSON" className="area-audit">
        <AuditTimeline events={events} currentRunId={snapshot?.scenario_run_id} />
      </Panel>
    </div>
  );
}
