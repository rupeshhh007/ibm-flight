import type { PilotSnapshot } from "../api/types";
import { formatVirtualTime, humanize } from "./format";
import { OBSERVATION_TONE } from "./tones";
import { Empty, Field, Panel, Pill } from "./ui";

function YesNo({ value, good }: { value: boolean; good: boolean }) {
  return <span className={value === good ? "text-ok" : "text-warn"}>{value ? "Yes" : "No"}</span>;
}

/**
 * One pilot's latest camera-derived OBSERVATION. Wording is deliberate: these are
 * uncertain observations, never a diagnosis, and UNKNOWN is never shown as a problem.
 */
export function PilotPanel({ pilot }: { pilot: PilotSnapshot }) {
  const obs = pilot.latest_observation ?? null;
  const label = pilot.pilot_id === "PILOT_1" ? "Pilot 1 · Captain seat" : "Pilot 2 · First officer seat";
  return (
    <Panel
      title={label}
      subtitle="Camera-derived observation — not a medical diagnosis"
      tone={obs ? OBSERVATION_TONE[obs.observation_status] : undefined}
      actions={obs ? <Pill tone={OBSERVATION_TONE[obs.observation_status]}>{humanize(obs.observation_status)}</Pill> : <Pill tone="muted">No data</Pill>}
    >
      {obs ? (
        <>
          <dl className="fields fields--2">
            <Field label="Camera available">
              <YesNo value={obs.camera_available} good />
            </Field>
            <Field label="Face visible">
              <YesNo value={obs.face_visible} good />
            </Field>
            <Field label="Eyes closed">
              <YesNo value={obs.eyes_closed} good={false} />
            </Field>
            <Field label="Window" mono>
              {(obs.observation_duration_ms / 1000).toFixed(1)} s
            </Field>
          </dl>
          <div className="quality" aria-label={`Observation quality ${Math.round(obs.observation_quality * 100)} percent`}>
            <div className="quality__head">
              <span>Observation quality</span>
              <span className="mono">{Math.round(obs.observation_quality * 100)}%</span>
            </div>
            <div className="quality__track">
              <div className="quality__fill" style={{ width: `${obs.observation_quality * 100}%` }} />
            </div>
          </div>
          {obs.observation_status === "UNKNOWN" && (
            <p className="note">Evidence unusable (camera unavailable, obstructed or low quality). UNKNOWN is not proof of incapacitation.</p>
          )}
          <p className="meta mono">Observed at {formatVirtualTime(obs.observed_at)} (virtual)</p>
        </>
      ) : (
        <Empty>No observation received for this run yet. Advance the scenario to produce synthetic observations.</Empty>
      )}
    </Panel>
  );
}
