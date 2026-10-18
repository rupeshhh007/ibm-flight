import { useMemo } from "react";
import { PILOT_IDS, type PilotObservation } from "../api/types";
import { Card, Chip, SectionHeader, Sparkline, SyntheticPilot } from "../components/console";
import { formatClock, humanize, pilotLabel } from "../components/format";
import { ObservationSummaryTable } from "../components/Insights";
import { OBSERVATION_TONE } from "../components/tones";
import { Empty } from "../components/ui";
import { eventsForRun, observationOf, observationSummary, pilotObservations } from "../hooks/selectors";
import { useAeroGuard } from "../hooks/useAeroGuard";

function eyesText(obs: PilotObservation): string {
  // Never report an eye state the camera could not observe.
  if (!obs.camera_available || !obs.face_visible) return "Not observable";
  return obs.eyes_closed ? "Yes" : "No";
}

export function VisionPage() {
  const { snapshot, events } = useAeroGuard();
  const runEvents = useMemo(() => eventsForRun(events, snapshot?.scenario_run_id), [events, snapshot?.scenario_run_id]);
  const summary = useMemo(() => observationSummary(runEvents), [runEvents]);
  const log = useMemo(
    () =>
      runEvents
        .map((e) => ({ seq: e.seq, obs: observationOf(e) }))
        .filter((r): r is { seq: number; obs: PilotObservation } => r.obs !== null)
        .reverse(),
    [runEvents],
  );

  if (!snapshot) return <Empty>Loading observations from the backend…</Empty>;

  return (
    <div className="view">
      <SectionHeader
        title="Vision analysis"
        subtitle="Camera-derived pilot observations · synthetic depictions, no image stream · not a medical diagnosis"
        actions={<Chip tone={summary.total ? "info" : "muted"}>{summary.total} observations this run</Chip>}
      />

      <div className="g-vision">
        {PILOT_IDS.map((id) => {
          const obs = snapshot.pilots.find((p) => p.pilot_id === id)?.latest_observation ?? null;
          const series = pilotObservations(runEvents, id).map((o) => o.obs.observation_quality);
          const tone = obs ? OBSERVATION_TONE[obs.observation_status] : "muted";
          return (
            <Card
              key={id}
              title={`${pilotLabel(id)} camera`}
              icon="camera"
              tone={tone}
              className="cam"
              actions={
                <>
                  <span className="cam__tag">Synthetic observation</span>
                  <Chip tone={tone}>{obs ? humanize(obs.observation_status) : "No data"}</Chip>
                </>
              }
            >
              <SyntheticPilot obs={obs} large />
              <div className="cam__foot">
                <div>
                  <span className="cam__label">Observation quality</span>
                  <span className="cam__value mono">{obs ? obs.observation_quality.toFixed(2) : "—"}</span>
                </div>
                <Sparkline values={series} tone={tone} label={`${pilotLabel(id)} observation quality this run`} />
              </div>
              {obs?.observation_status === "UNKNOWN" && (
                <p className="hint">
                  {!obs.camera_available || !obs.face_visible
                    ? "Evidence unusable (camera unavailable or face not visible). UNKNOWN is not proof of incapacitation."
                    : "Evidence insufficient for a determination. UNKNOWN is not proof of incapacitation."}
                </p>
              )}
            </Card>
          );
        })}

        <div className="stack">
          <Card title="Observation fields" icon="list" flush>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Field</th>
                    {PILOT_IDS.map((id) => (
                      <th key={id} scope="col">
                        {pilotLabel(id)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(
                    [
                      ["Status", (o: PilotObservation) => humanize(o.observation_status)],
                      ["Camera available", (o: PilotObservation) => (o.camera_available ? "Yes" : "No")],
                      ["Face visible", (o: PilotObservation) => (o.face_visible ? "Yes" : "No")],
                      ["Eyes closed", eyesText],
                      ["Window", (o: PilotObservation) => `${(o.observation_duration_ms / 1000).toFixed(1)} s`],
                      ["Quality", (o: PilotObservation) => o.observation_quality.toFixed(2)],
                      ["Observed", (o: PilotObservation) => formatClock(o.observed_at)],
                    ] as [string, (o: PilotObservation) => string][]
                  ).map(([label, fn]) => (
                    <tr key={label}>
                      <td className="muted-text">{label}</td>
                      {PILOT_IDS.map((id) => {
                        const obs = snapshot.pilots.find((p) => p.pilot_id === id)?.latest_observation ?? null;
                        return (
                          <td key={id} className="mono">
                            {obs ? fn(obs) : "—"}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          <Card title="Observation analysis" icon="vision">
            <ObservationSummaryTable summary={summary} />
          </Card>
        </div>
      </div>

      <Card title={`Observation log (${log.length})`} icon="clock" flush>
        {log.length === 0 ? (
          <Empty icon="camera">No observations in this run yet. Advance the scenario to produce synthetic observations.</Empty>
        ) : (
          <div className="table-wrap table-wrap--scroll" tabIndex={0} role="region" aria-label="Observation log, scrollable">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col" className="num">Seq</th>
                  <th scope="col">Virtual time</th>
                  <th scope="col">Pilot</th>
                  <th scope="col">Status</th>
                  <th scope="col">Camera</th>
                  <th scope="col">Face</th>
                  <th scope="col">Eyes closed</th>
                  <th scope="col" className="num">Quality</th>
                </tr>
              </thead>
              <tbody>
                {log.map(({ seq, obs }) => (
                  <tr key={seq}>
                    <td className="mono num muted-text">{seq}</td>
                    <td className="mono">{formatClock(obs.observed_at)}</td>
                    <td>{pilotLabel(obs.pilot_id)}</td>
                    <td>
                      <Chip tone={OBSERVATION_TONE[obs.observation_status]}>{humanize(obs.observation_status)}</Chip>
                    </td>
                    <td>{obs.camera_available ? "Available" : "Unavailable"}</td>
                    <td>{obs.face_visible ? "Visible" : "Not visible"}</td>
                    <td>{eyesText(obs)}</td>
                    <td className="mono num">{obs.observation_quality.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
