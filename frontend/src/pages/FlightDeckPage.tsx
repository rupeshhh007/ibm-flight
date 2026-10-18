import { useMemo } from "react";
import { PILOT_IDS, type PilotSnapshot } from "../api/types";
import { Chip, flightStatus, Sparkline, StatusTile, TelemetryStrip } from "../components/console";
import { formatClock, formatHeading, formatNumber, humanize, pilotLabel, shortId } from "../components/format";
import { Icon } from "../components/icons";
import { FlightScene } from "../components/scene/FlightScene";
import { GUARDIAN_TONE, OBSERVATION_TONE, SENTINEL_TONE } from "../components/tones";
import { concernCounts, eventsForRun, incidentEventTime, observationSummary, pilotObservations, runMilestones, sceneSamples } from "../hooks/selectors";
import { useAeroGuard } from "../hooks/useAeroGuard";

function PilotStatusCard({ pilot, qualities, compact = false }: { pilot: PilotSnapshot; qualities: number[]; compact?: boolean }) {
  const obs = pilot.latest_observation ?? null;
  const tone = obs ? OBSERVATION_TONE[obs.observation_status] : "muted";
  return (
    <div className={`pcard pcard--${tone}`}>
      <div className="pcard__head">
        <Icon name="user" size={14} />
        <span className="pcard__name">
          {pilotLabel(pilot.pilot_id)} <span className="pcard__seat">({pilot.pilot_id === "PILOT_1" ? "Captain" : "First Officer"})</span>
        </span>
      </div>
      <div className={`pcard__status pcard__status--${tone}`}>
        <Icon name={obs?.observation_status === "RESPONSIVE" ? "check" : obs ? "alert" : "info"} size={15} />
        {obs ? humanize(obs.observation_status) : "No observation"}
      </div>
      {!compact && (
      <div className="pcard__row pcard__row--spark">
        <span className="pcard__metric">
          <span>Observation quality</span>
          <span className="mono pcard__value">{obs ? obs.observation_quality.toFixed(2) : "—"}</span>
          <span className="mono">Last {obs ? formatClock(obs.observed_at) : "—"}</span>
        </span>
        <Sparkline values={qualities} tone={tone} label={`${pilotLabel(pilot.pilot_id)} observation quality this run`} />
      </div>
      )}
    </div>
  );
}

export function FlightDeckPage() {
  const { snapshot, scenarios, events, pending, commands } = useAeroGuard();
  const runEvents = useMemo(() => eventsForRun(events, snapshot?.scenario_run_id), [events, snapshot?.scenario_run_id]);
  const samples = useMemo(() => sceneSamples(runEvents), [runEvents]);
  const incident = snapshot?.active_incident ?? null;
  const incidentAt = useMemo(() => incidentEventTime(runEvents, incident?.incident_id), [runEvents, incident?.incident_id]);
  const concerns = useMemo(() => concernCounts(runEvents), [runEvents]);
  const summary = useMemo(() => observationSummary(runEvents), [runEvents]);
  const milestones = useMemo(() => runMilestones(runEvents), [runEvents]);
  const qualities = useMemo(
    () => Object.fromEntries(PILOT_IDS.map((id) => [id, pilotObservations(runEvents, id).map((o) => o.obs.observation_quality)])),
    [runEvents],
  );

  const status = flightStatus(snapshot);
  const t = snapshot?.telemetry ?? null;
  const emergency = Boolean(incident);
  const scenarioName = scenarios?.find((s) => s.scenario_id === snapshot?.scenario_id)?.name ?? snapshot?.scenario_id ?? "No scenario";
  const pilots = PILOT_IDS.map((id) => snapshot?.pilots.find((p) => p.pilot_id === id) ?? { pilot_id: id, latest_observation: null });
  const link = snapshot?.communication.atc_link_connected ?? false;
  const action = snapshot?.last_simulator_action ?? null;

  return (
    <div className="deck">
      <section className={`hero hero--${status.tone}`} aria-label="Flight deck">
        <FlightScene
          samples={samples}
          incidentAt={incidentAt}
          incidentLabel={incident ? humanize(incident.incident_type) : null}
          emergency={emergency}
          actionLabel={action ? `SYMBOLIC ACTION ${humanize(action.result).toUpperCase()}: ${action.action_type}` : null}
        />
        <div className="hero__overlay">
          <div className="hero__top">
            <TelemetryStrip snapshot={snapshot} overlay />
          </div>

          <aside className={`fstatus fstatus--${status.tone}`} aria-label="Flight status">
            <span className="fstatus__label">Flight status</span>
            <span className="fstatus__value">{status.label}</span>
            <span className="fstatus__detail">{status.detail}</span>
            <div className="fstatus__ac">
              <span className="mono">{t?.aircraft_id ?? "No aircraft"}</span>
              <span className="fstatus__sub">Synthetic simulated aircraft</span>
            </div>
            <dl className="fstatus__grid">
              <div>
                <dt>Altitude</dt>
                <dd className="mono">{t ? `${formatNumber(t.altitude_ft)} ft` : "—"}</dd>
              </div>
              <div>
                <dt>Speed</dt>
                <dd className="mono">{t ? `${formatNumber(t.airspeed_kts)} kt` : "—"}</dd>
              </div>
              <div>
                <dt>Heading</dt>
                <dd className="mono">{t ? formatHeading(t.heading_deg) : "—"}</dd>
              </div>
              <div>
                <dt>Phase</dt>
                <dd>{t ? humanize(t.flight_phase) : "—"}</dd>
              </div>
            </dl>
            {/* Real telemetry field active_warning_codes (restored); never synthesised client-side. */}
            <div className="fstatus__warn" aria-label="Telemetry warning codes">
              <span className="fstatus__label">Warning codes</span>
              {t && t.active_warning_codes.length > 0 ? (
                t.active_warning_codes.map((code) => (
                  <Chip key={code} tone="warn">
                    {code}
                  </Chip>
                ))
              ) : (
                <span className="fstatus__none">{t ? "None active" : "—"}</span>
              )}
            </div>
            {incident ? (
              <div className="fstatus__incident">
                <span className="fstatus__label">Active incident</span>
                <strong className="mono">{incident.incident_type}</strong>
                <span>
                  {humanize(incident.severity)} · {humanize(incident.guardian_state)}
                </span>
                <span className="fstatus__bar" aria-hidden="true" />
              </div>
            ) : (
              <div className="fstatus__scenario">
                <span className="fstatus__label">Active scenario</span>
                <strong>{scenarioName}</strong>
                <span className="mono">
                  {snapshot?.scenario_run_id ? `Run ${shortId(snapshot.scenario_run_id)} · T ${formatClock(snapshot.virtual_time)}` : "Start one from Scenarios"}
                </span>
              </div>
            )}
          </aside>

          <aside className="hero__right">
            {incident && snapshot && (
              <div className="gpanel" role="group" aria-label="Guardian escalation">
                <div className="gpanel__head">
                  <Icon name="alert" size={22} />
                  <div>
                    <span className="gpanel__label">Guardian status</span>
                    <span className="gpanel__value">{humanize(snapshot.guardian_state)}</span>
                  </div>
                </div>
                <span className="gpanel__sub">
                  {snapshot.sentinel_state === "AWAITING_ATC" ? "Awaiting ATC decision" : `Sentinel ${humanize(snapshot.sentinel_state).toLowerCase()}`}
                </span>
                <ul className="gpanel__list">
                  <li>
                    <Icon name="user" size={14} /> Pilot 1: {concerns.PILOT_1} concern observation{concerns.PILOT_1 === 1 ? "" : "s"}
                  </li>
                  <li>
                    <Icon name="user" size={14} /> Pilot 2: {concerns.PILOT_2} concern observation{concerns.PILOT_2 === 1 ? "" : "s"}
                  </li>
                  <li>
                    <Icon name="list" size={14} /> Evidence collected: {incident.evidence_event_ids.length} observations
                  </li>
                  <li>
                    <Icon name="clock" size={14} /> Incident raised: {formatClock(incident.created_at)}
                  </li>
                </ul>
                <div className="gpanel__actions">
                  <a className="btn btn--danger-solid btn--sm" href="#sentinel">
                    Open Sentinel console <Icon name="chevron" size={12} />
                  </a>
                  {PILOT_IDS.map((id) => (
                    <button key={id} type="button" className="btn btn--ghost btn--sm" disabled={pending !== null} onClick={() => commands.acknowledge(id)}>
                      Acknowledge as {pilotLabel(id)}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {pilots.map((p) => (
              <PilotStatusCard key={p.pilot_id} pilot={p} qualities={qualities[p.pilot_id] ?? []} compact={emergency} />
            ))}
          </aside>

          <p className="hero__caption">Synthetic scene · illustrative route · waypoints are telemetry samples · not for navigation</p>
        </div>
      </section>

      <div className="deck__status">
        <StatusTile icon="shield" title="Guardian" value={snapshot ? humanize(snapshot.guardian_state) : "—"} tone={snapshot ? GUARDIAN_TONE[snapshot.guardian_state] : "muted"} detail={incident ? "Incident active" : "Monitoring"} />
        <StatusTile icon="radar" title="Sentinel" value={snapshot ? humanize(snapshot.sentinel_state) : "—"} tone={snapshot ? SENTINEL_TONE[snapshot.sentinel_state] : "muted"} detail={`ATC link ${link ? "connected" : "disconnected"}`} />
        <StatusTile icon="vision" title="Vision" value={`${summary.total} observations`} tone={summary.total ? "info" : "muted"} detail={`${summary.cameraUnavailable} camera-unavailable this run`} />
        <StatusTile icon="plane" title="Simulator" value={t ? humanize(t.flight_phase) : snapshot?.scenario_run_id ? "Running" : "Idle"} tone={snapshot?.scenario_run_id ? "info" : "muted"} detail={action ? `Last action ${action.action_type}` : "No action executed"} />
        <div className="scard">
          <div className="scard__col">
            <span className="scard__label">Scenario</span>
            <strong className={emergency ? "text-alert" : ""}>{scenarioName}</strong>
            <span className="mono scard__meta">{snapshot?.scenario_run_id ? `Run ${shortId(snapshot.scenario_run_id)}` : "No active run"}</span>
          </div>
          <div className="scard__col">
            <span className="scard__label">Progress</span>
            <strong className="mono">{runEvents.length} events</strong>
            <span className="scard__meta">
              {milestones.length} milestones · T {formatClock(snapshot?.virtual_time)}
            </span>
            <div className="scard__ticks" aria-hidden="true">
              {milestones.slice(-14).map((m) => (
                <span key={m.seq} className={`scard__tick scard__tick--${m.tone}`} />
              ))}
            </div>
          </div>
          <Chip tone={status.tone} live={status.tone === "alert"}>
            {status.label}
          </Chip>
        </div>
      </div>
    </div>
  );
}
