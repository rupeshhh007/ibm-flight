import { useMemo } from "react";
import { isEventOfType, PILOT_IDS, type StoredEvent } from "../api/types";
import { Card, Chip, SectionHeader, Sparkline, SyntheticPilot } from "../components/console";
import { formatClock, humanize, pilotLabel, shortId } from "../components/format";
import { Icon, type IconName } from "../components/icons";
import { EvidenceTable } from "../components/StatePanels";
import { GUARDIAN_ALTERNATES, GUARDIAN_TONE, GUARDIAN_TRACK, OBSERVATION_TONE, type Tone } from "../components/tones";
import { Empty, StateTrack } from "../components/ui";
import { eventsForRun, pilotObservations, resolveEvidence } from "../hooks/selectors";
import { useAeroGuard } from "../hooks/useAeroGuard";

interface TimelineItem {
  seq: number;
  at: string;
  icon: IconName;
  tone: Tone;
  title: string;
  detail: string;
}

/** Guardian-relevant moments of the run: concern/unknown observations, incidents, acknowledgements. */
function guardianTimeline(events: readonly StoredEvent[]): TimelineItem[] {
  const out: TimelineItem[] = [];
  for (const e of events) {
    if (isEventOfType(e, "PILOT_OBSERVATION") && e.payload.observation_status !== "RESPONSIVE") {
      const unknown = e.payload.observation_status === "UNKNOWN";
      out.push({
        seq: e.seq,
        at: e.occurred_at,
        icon: unknown ? "eyeOff" : "alert",
        tone: unknown ? "muted" : "warn",
        title: `${pilotLabel(e.payload.pilot_id)} ${unknown ? "observation unknown" : "concern observed"}`,
        detail: `${humanize(e.payload.observation_status)} · quality ${e.payload.observation_quality.toFixed(2)}`,
      });
    } else if (isEventOfType(e, "GUARDIAN_INCIDENT")) {
      out.push({ seq: e.seq, at: e.occurred_at, icon: "shield", tone: "alert", title: "Incident escalated", detail: e.payload.incident_type });
    } else if (isEventOfType(e, "PILOT_ACKNOWLEDGED")) {
      out.push({ seq: e.seq, at: e.occurred_at, icon: "check", tone: "ok", title: `${pilotLabel(e.payload.pilot_id)} acknowledged`, detail: "Acknowledgement sent to Guardian" });
    }
  }
  return out;
}

export function GuardianPage() {
  const { snapshot, events, pending, commands } = useAeroGuard();
  const runEvents = useMemo(() => eventsForRun(events, snapshot?.scenario_run_id), [events, snapshot?.scenario_run_id]);
  const timeline = useMemo(() => guardianTimeline(runEvents), [runEvents]);
  const incident = snapshot?.active_incident ?? null;
  const evidence = useMemo(() => (incident ? resolveEvidence(runEvents, incident.evidence_event_ids) : []), [runEvents, incident]);

  if (!snapshot) return <Empty>Loading Guardian state from the backend…</Empty>;
  const tone = GUARDIAN_TONE[snapshot.guardian_state];

  return (
    <div className="view">
      <SectionHeader
        title="Guardian"
        subtitle="Pilot monitoring & incident detection · camera observations are not diagnoses"
        tone={tone}
        actions={
          <Chip tone={tone} live={snapshot.guardian_state === "ESCALATED"}>
            Guardian {humanize(snapshot.guardian_state)}
          </Chip>
        }
      />

      <div className="g3">
        <div className="stack">
          {PILOT_IDS.map((id) => {
            const pilot = snapshot.pilots.find((p) => p.pilot_id === id);
            const obs = pilot?.latest_observation ?? null;
            const series = pilotObservations(runEvents, id).map((o) => o.obs.observation_quality);
            const ptone = obs ? OBSERVATION_TONE[obs.observation_status] : "muted";
            return (
              <Card key={id} title={pilotLabel(id)} icon="user" tone={ptone} className="pilot-block">
                <div className="pilot-block__body">
                  <SyntheticPilot obs={obs} />
                  <div className="pilot-block__side">
                    <Chip tone={ptone}>{obs ? humanize(obs.observation_status) : "No observation"}</Chip>
                    <Sparkline values={series} tone={ptone} label={`${pilotLabel(id)} observation quality this run`} />
                    <div className="pilot-block__q">
                      <span>Quality</span>
                      <span className="mono">{obs ? obs.observation_quality.toFixed(2) : "—"}</span>
                    </div>
                  </div>
                </div>
                {!obs && <p className="hint">No observation received for this run yet.</p>}
              </Card>
            );
          })}
        </div>

        <Card title="Observation timeline" icon="clock">
          {timeline.length === 0 ? (
            <Empty icon="clock">No concern or unknown observations in this run.</Empty>
          ) : (
            <ol className="vtl" tabIndex={0} aria-label="Guardian observation timeline">
              {timeline.map((item) => (
                <li key={item.seq} className={`vtl__item vtl__item--${item.tone}`}>
                  <span className="vtl__time mono">{formatClock(item.at)}</span>
                  <span className="vtl__node" aria-hidden="true">
                    <Icon name={item.icon} size={12} />
                  </span>
                  <span className="vtl__text">
                    <strong>{item.title}</strong>
                    <span>{item.detail}</span>
                  </span>
                </li>
              ))}
            </ol>
          )}
        </Card>

        <Card title="Incident details" icon="alert" tone={incident ? (incident.severity === "CRITICAL" ? "alert" : "warn") : undefined}>
          {incident ? (
            <div className="idetail">
              <div className="idetail__head">
                <span className="mono idetail__id">INC-{shortId(incident.incident_id)}</span>
                <Chip tone={incident.severity === "CRITICAL" ? "alert" : "warn"}>{humanize(incident.severity)}</Chip>
              </div>
              <dl className="idetail__grid">
                <dt>Type</dt>
                <dd className="mono text-alert">{incident.incident_type}</dd>
                <dt>State</dt>
                <dd className="text-alert">{humanize(incident.guardian_state)}</dd>
                <dt>Evidence</dt>
                <dd>{incident.evidence_event_ids.length} observations</dd>
                <dt>Raised at</dt>
                <dd className="mono">{formatClock(incident.created_at)}</dd>
                <dt>Run</dt>
                <dd className="mono">{shortId(incident.scenario_run_id)}</dd>
                <dt>Explanation</dt>
                <dd>{incident.explanation}</dd>
              </dl>
              <div className="btn-row">
                <button type="button" className="btn btn--secondary btn--sm" onClick={() => document.getElementById("guardian-evidence")?.scrollIntoView({ behavior: "smooth", block: "start" })}>
                  View evidence <Icon name="chevron" size={12} />
                </button>
                <a className="btn btn--ghost btn--sm" href="#blackbox">
                  Open Black Box
                </a>
              </div>
            </div>
          ) : (
            <Empty icon="shield">
              {snapshot.guardian_state === "NORMAL"
                ? "No active incident. Guardian raises one only from documented multi-observation evidence."
                : `Guardian state is ${humanize(snapshot.guardian_state)} and there is no active incident.`}
            </Empty>
          )}
        </Card>
      </div>

      <Card title="State progression" icon="route">
        <StateTrack label="Guardian escalation level" steps={GUARDIAN_TRACK} alternates={GUARDIAN_ALTERNATES} current={snapshot.guardian_state} toneOf={GUARDIAN_TONE} format={humanize} />
      </Card>

      <div className="g2">
        <Card title={incident ? `Evidence (${evidence.filter((e) => e.event).length}/${evidence.length})` : "Evidence"} icon="list" className="anchor" flush>
          <div id="guardian-evidence" />
          {incident ? <EvidenceTable evidence={evidence} /> : <Empty>Evidence appears with an active incident.</Empty>}
        </Card>
        <Card title="Pilot acknowledgement" icon="check">
          {incident ? (
            <div className="ack">
              <p className="hint">Sent to the backend for the active incident (alert {shortId(incident.incident_id)}). Guardian decides what it means.</p>
              <div className="btn-row">
                {PILOT_IDS.map((id) => (
                  <button key={id} type="button" className="btn btn--primary" disabled={pending !== null} onClick={() => commands.acknowledge(id)}>
                    Acknowledge as {pilotLabel(id)}
                  </button>
                ))}
              </div>
            </div>
          ) : snapshot.guardian_state !== "NORMAL" ? (
            <Empty icon="shield">Guardian state is {humanize(snapshot.guardian_state)} and there is no active incident. Acknowledgement is accepted only for an active incident.</Empty>
          ) : (
            <Empty icon="shield">No active incident. Acknowledgement controls appear when Guardian raises an alert.</Empty>
          )}
        </Card>
      </div>
    </div>
  );
}
