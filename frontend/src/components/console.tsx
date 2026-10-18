// Console building blocks shared by the six views. Everything here renders real
// backend values; illustrations are explicitly labelled as synthetic.
import type { ReactNode } from "react";
import type { PilotObservation, SystemSnapshot } from "../api/types";
import { formatClock, formatFlightLevel, formatHeading, formatNumber, humanize, shortId } from "./format";
import { Icon, type IconName } from "./icons";
import { OBSERVATION_TONE, type Tone } from "./tones";

/** Overall flight status derived only from the snapshot (never assumed). */
export function flightStatus(snapshot: SystemSnapshot | null): { label: string; tone: Tone; detail: string } {
  if (!snapshot) return { label: "No data", tone: "muted", detail: "Waiting for backend state" };
  if (!snapshot.scenario_run_id) return { label: "Standby", tone: "muted", detail: "No scenario running" };
  if (snapshot.active_incident) {
    return { label: "Emergency", tone: "alert", detail: `${humanize(snapshot.active_incident.incident_type)} · ${humanize(snapshot.active_incident.severity)}` };
  }
  if (snapshot.guardian_state !== "NORMAL") return { label: "Advisory", tone: "warn", detail: `Guardian ${humanize(snapshot.guardian_state).toLowerCase()}` };
  return { label: "Normal", tone: "ok", detail: "No active incident" };
}

/** Page section header with the reference's left accent bar. */
export function SectionHeader({ title, subtitle, tone = "info", actions }: { title: string; subtitle: string; tone?: Tone; actions?: ReactNode }) {
  return (
    <header className={`section-head section-head--${tone}`}>
      <div>
        <h1 className="section-head__title">{title}</h1>
        <p className="section-head__sub">{subtitle}</p>
      </div>
      {actions && <div className="section-head__actions">{actions}</div>}
    </header>
  );
}

/** Thin-bordered console panel with an uppercase caption. */
export function Card({
  title,
  icon,
  tone,
  actions,
  children,
  className = "",
  flush = false,
}: {
  title?: string;
  icon?: IconName;
  tone?: Tone;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  flush?: boolean;
}) {
  return (
    <section className={`card ${tone ? `card--${tone}` : ""} ${className}`} aria-label={title}>
      {title && (
        <header className="card__head">
          <h2 className="card__title">
            {icon && <Icon name={icon} size={14} />}
            {title}
          </h2>
          {actions && <div className="card__actions">{actions}</div>}
        </header>
      )}
      <div className={`card__body ${flush ? "card__body--flush" : ""}`}>{children}</div>
    </section>
  );
}

/** Status chip; text always states the status (colour is never the only signal). */
export function Chip({ tone, children, live = false, icon }: { tone: Tone; children: ReactNode; live?: boolean; icon?: IconName }) {
  return (
    <span className={`chip chip--${tone} ${live ? "chip--live" : ""}`}>
      {icon ? <Icon name={icon} size={12} /> : <span className="chip__dot" aria-hidden="true" />}
      {children}
    </span>
  );
}

/** Real observation-quality series as a small line chart (not a waveform). */
export function Sparkline({ values, tone = "info", label }: { values: number[]; tone?: Tone; label: string }) {
  const w = 120;
  const h = 34;
  if (values.length === 0) return <span className="spark spark--empty">No samples</span>;
  const pts = values.map((v, i) => {
    const x = values.length === 1 ? w / 2 : (i / (values.length - 1)) * (w - 6) + 3;
    const y = h - 4 - Math.max(0, Math.min(1, v)) * (h - 8);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return (
    <svg className={`spark spark--${tone}`} viewBox={`0 0 ${w} ${h}`} role="img" aria-label={`${label}: ${values.map((v) => v.toFixed(2)).join(", ")}`}>
      <line x1="0" y1={h - 4} x2={w} y2={h - 4} className="spark__base" />
      <polyline points={pts.join(" ")} className="spark__line" />
      {pts.map((p, i) => {
        const [x, y] = p.split(",");
        return <circle key={i} cx={x} cy={y} r={i === pts.length - 1 ? 2.6 : 1.6} className="spark__dot" />;
      })}
    </svg>
  );
}

/**
 * Synthetic observation figure: a stylised seat and pilot silhouette coloured by
 * the observation's fields. It is NOT a camera image and says so.
 */
export function SyntheticPilot({ obs, large = false }: { obs: PilotObservation | null; large?: boolean }) {
  const tone: Tone = obs ? OBSERVATION_TONE[obs.observation_status] : "muted";
  const camera = obs?.camera_available ?? false;
  const face = obs?.face_visible ?? false;
  const eyesKnown = camera && face;
  return (
    <figure className={`synth synth--${tone} ${large ? "synth--large" : ""}`}>
      <svg viewBox="0 0 200 140" role="img" aria-label={obs ? `Synthetic depiction: ${humanize(obs.observation_status)}; camera ${camera ? "available" : "unavailable"}; face ${face ? "visible" : "not visible"}` : "No observation yet"}>
        <defs>
          <pattern id={`synth-hatch-${large ? "l" : "s"}`} width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="8" stroke="#8aa0bd" strokeOpacity="0.35" strokeWidth="3" />
          </pattern>
        </defs>
        <rect x="0" y="0" width="200" height="140" className="synth__bg" />
        {/* cockpit frame lines for context */}
        <path d="M0 30 L40 18 L160 18 L200 30" className="synth__frame" />
        <path d="M0 140 L28 70 M200 140 L172 70" className="synth__frame" />
        {/* seat */}
        <path d="M70 140 L66 62 Q66 38 100 36 Q134 38 134 62 L130 140 Z" className="synth__seat" />
        {obs && (
          <g className="synth__pilot">
            <path d="M58 140 Q60 104 100 100 Q140 104 142 140 Z" className="synth__body" />
            <ellipse cx="100" cy="74" rx="19" ry="23" className="synth__head" />
            {eyesKnown &&
              (obs.eyes_closed ? (
                <g className="synth__eyes">
                  <path d="M89 74 q4 3 8 0" />
                  <path d="M103 74 q4 3 8 0" />
                </g>
              ) : (
                <g className="synth__eyes">
                  <circle cx="93" cy="73" r="2" />
                  <circle cx="107" cy="73" r="2" />
                </g>
              ))}
          </g>
        )}
        {obs && !camera && <rect x="0" y="0" width="200" height="140" fill={`url(#synth-hatch-${large ? "l" : "s"})`} />}
        {/* corner brackets */}
        <path d="M8 22 V8 H22 M178 8 H192 V22 M192 118 V132 H178 M22 132 H8 V118" className="synth__brackets" />
        {obs && face && camera && <rect x="78" y="48" width="44" height="52" className="synth__facebox" />}
      </svg>
      <figcaption>
        <span>{!obs ? "No observation" : !camera ? "Camera unavailable" : !face ? "Face not visible" : "Face visible"}</span>
        <span className="synth__note">Synthetic · no camera image</span>
      </figcaption>
    </figure>
  );
}

/** Bottom status row tile (Guardian / Sentinel / Vision / Simulator). */
export function StatusTile({ icon, title, value, tone, detail }: { icon: IconName; title: string; value: string; tone: Tone; detail?: string }) {
  return (
    <div className={`stile stile--${tone}`}>
      <span className="stile__icon" aria-hidden="true">
        <Icon name={icon} size={20} />
      </span>
      <div className="stile__text">
        <span className="stile__title">{title}</span>
        <span className="stile__value">{value}</span>
        {detail && <span className="stile__detail">{detail}</span>}
      </div>
      <span className={`stile__dot`} aria-hidden="true" />
    </div>
  );
}

/** Compact telemetry strip (real snapshot values; flight level is derived from altitude). */
export function TelemetryStrip({ snapshot, overlay = false }: { snapshot: SystemSnapshot | null; overlay?: boolean }) {
  const t = snapshot?.telemetry ?? null;
  const cells: [string, string][] = [
    ["Aircraft ID", t?.aircraft_id ?? "—"],
    ["FL (derived)", t ? formatFlightLevel(t.altitude_ft) : "—"],
    ["IAS", t ? `${formatNumber(t.airspeed_kts)} KT` : "—"],
    ["Heading", t ? formatHeading(t.heading_deg) : "—"],
    ["Altitude", t ? `${formatNumber(t.altitude_ft)} FT` : "—"],
    ["Sim time", formatClock(snapshot?.virtual_time)],
  ];
  if (!overlay) {
    cells.push(["Scenario", snapshot ? (snapshot.scenario_id ?? "None") : "—"], ["Run", shortId(snapshot?.scenario_run_id)]);
  }
  return (
    <section className={`tstrip ${overlay ? "tstrip--overlay" : ""}`} aria-label="Flight telemetry">
      {cells.map(([label, value]) => (
        <div key={label} className="tstrip__cell">
          <span className="tstrip__label">{label}</span>
          <span className="tstrip__value">{value}</span>
        </div>
      ))}
    </section>
  );
}

/** Small scenario illustrations (synthetic symbols, not photos). */
export function ScenarioArt({ id }: { id: string }) {
  const seat = (x: number, tone: "ok" | "alert" | "muted", hatched = false) => (
    <g transform={`translate(${x} 0)`} className={`sart__seat sart__seat--${tone}`}>
      <path d="M-22 92 L-24 44 Q-24 26 0 25 Q24 26 24 44 L22 92 Z" className="sart__chair" />
      <ellipse cx="0" cy="44" rx="11" ry="13" className="sart__head" />
      <path d="M-20 92 Q-18 66 0 64 Q18 66 20 92 Z" className="sart__body" />
      {hatched && <rect x="-30" y="20" width="60" height="74" className="sart__hatch" />}
    </g>
  );
  const tower = (connected: boolean) => (
    <g transform="translate(170 0)" className={`sart__tower ${connected ? "" : "sart__tower--down"}`}>
      <path d="M-6 92 L-3 40 L3 40 L6 92 Z" />
      <path d="M-12 40 L12 40 L9 30 L-9 30 Z" />
      <path d="M-18 22 Q0 6 18 22" className="sart__waves" />
      <path d="M-26 16 Q0 -8 26 16" className="sart__waves" />
    </g>
  );
  let body: ReactNode;
  switch (id) {
    case "normal_flight":
      body = (
        <>
          {seat(70, "ok")}
          {seat(130, "ok")}
        </>
      );
      break;
    case "single_pilot_unresponsive":
      body = (
        <>
          {seat(70, "alert")}
          {seat(130, "ok")}
        </>
      );
      break;
    case "dual_pilot_atc_connected":
      body = (
        <>
          {seat(50, "alert")}
          {seat(105, "alert")}
          {tower(true)}
        </>
      );
      break;
    case "dual_pilot_atc_disconnected":
      body = (
        <>
          {seat(50, "alert")}
          {seat(105, "alert")}
          {tower(false)}
        </>
      );
      break;
    case "camera_obstructed":
      body = (
        <>
          {seat(70, "muted", true)}
          {seat(130, "muted", true)}
        </>
      );
      break;
    default:
      body = seat(100, "muted");
  }
  return (
    <svg className="sart" viewBox="0 0 200 100" aria-hidden="true">
      <rect width="200" height="100" className="sart__bg" />
      {body}
    </svg>
  );
}

/** Simulated ATC ↔ aircraft link illustration (Sentinel view). */
export function LinkScene({ connected, emergency, aircraftId }: { connected: boolean; emergency: boolean; aircraftId: string }) {
  return (
    <svg className={`link-scene ${connected ? "" : "link-scene--down"} ${emergency ? "link-scene--emergency" : ""}`} viewBox="0 0 800 300" role="img"
      aria-label={`Simulated ATC link ${connected ? "connected" : "disconnected"} with ${aircraftId}`}>
      <defs>
        <radialGradient id="ls-glow" cx="50%" cy="100%" r="80%">
          <stop offset="0%" stopColor="#1a4f7a" stopOpacity="0.6" />
          <stop offset="100%" stopColor="#020611" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="800" height="300" className="link-scene__bg" />
      <ellipse cx="400" cy="420" rx="640" ry="230" fill="url(#ls-glow)" />
      {[0, 1, 2, 3].map((i) => (
        <ellipse key={i} cx="400" cy="420" rx={640 - i * 110} ry={230 - i * 40} className="link-scene__grid" />
      ))}
      {/* tower */}
      <g transform="translate(150 250)" className="link-scene__tower">
        <path d="M-10 0 L-5 -110 L5 -110 L10 0 Z" />
        <path d="M-26 -110 L26 -110 L20 -132 L-20 -132 Z" />
        <rect x="-16" y="-128" width="32" height="12" className="link-scene__glass" />
        <text x="0" y="28" textAnchor="middle" className="link-scene__label">SIMULATED ATC</text>
      </g>
      {/* link arc */}
      <path d="M180 110 Q 400 -10 620 120" className="link-scene__arc" />
      <g transform="translate(400 48)">
        <rect x="-100" y="-17" width="200" height="32" rx="3" className="link-scene__badge" />
        <text x="0" y="4" textAnchor="middle" className="link-scene__badge-text">{connected ? "SIMULATED LINK" : "LINK DOWN"}</text>
      </g>
      {/* aircraft */}
      <g transform="translate(640 150) rotate(-12) scale(0.55)" className="link-scene__aircraft">
        <path d="M-150 0 L-40 -8 L20 -70 L44 -70 L10 -8 L120 -6 Q150 0 120 6 L10 8 L44 70 L20 70 L-40 8 L-150 0 Z" />
      </g>
      <text x="640" y="232" textAnchor="middle" className="link-scene__label">{aircraftId}</text>
      {emergency && <circle cx="640" cy="150" r="58" className="link-scene__alert" />}
    </svg>
  );
}
