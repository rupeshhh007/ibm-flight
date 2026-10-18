// Cinematic flight scene, drawn entirely as local SVG (no images, no map tiles,
// no external services). The terrain, city lights and route geometry are
// ILLUSTRATIVE; the waypoints are the run's real TELEMETRY_UPDATED samples placed
// along the route by virtual time, and the incident zone is the sample at which
// Guardian's incident was committed. The simulator reports a fixed position, so
// geographic placement would be meaningless — the caption says so on screen.
import { memo, useMemo } from "react";
import type { AircraftTelemetry } from "../../api/types";
import { formatClock, formatFlightLevel, formatNumber, humanize } from "../format";

export interface SceneSample {
  at: string;
  telemetry: AircraftTelemetry;
}

const W = 1600;
const H = 720;

// Route: a sweeping cubic Bézier from lower left to upper right (as in the reference composition).
const P0 = { x: 40, y: 640 };
const P1 = { x: 520, y: 640 };
const P2 = { x: 860, y: 300 };
const P3 = { x: 1580, y: 250 };

function bezier(t: number) {
  const u = 1 - t;
  return {
    x: u * u * u * P0.x + 3 * u * u * t * P1.x + 3 * u * t * t * P2.x + t * t * t * P3.x,
    y: u * u * u * P0.y + 3 * u * u * t * P1.y + 3 * u * t * t * P2.y + t * t * t * P3.y,
  };
}

// Arc-length lookup so "fraction of route" maps to evenly spaced distance.
const LUT = (() => {
  const pts = Array.from({ length: 401 }, (_, i) => bezier(i / 400));
  const len = [0];
  for (let i = 1; i < pts.length; i += 1) len.push(len[i - 1] + Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y));
  return { pts, len, total: len[len.length - 1] };
})();

function pointAt(fraction: number) {
  const target = Math.min(Math.max(fraction, 0), 1) * LUT.total;
  let i = LUT.len.findIndex((l) => l >= target);
  if (i <= 0) i = 1;
  const a = LUT.pts[i - 1];
  const b = LUT.pts[i];
  const seg = LUT.len[i] - LUT.len[i - 1] || 1;
  const k = (target - LUT.len[i - 1]) / seg;
  return { x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k, angle: (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI };
}

function pathBetween(from: number, to: number, steps = 60) {
  const pts = Array.from({ length: steps + 1 }, (_, i) => pointAt(from + ((to - from) * i) / steps));
  return pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
}

/** Deterministic PRNG so the generated terrain is identical on every render. */
function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const PLANET = { cx: 800, cy: 2050, r: 1840 };

/** Static backdrop: planet limb, terrain texture, clouds, city lights and stars. Rendered once. */
const Backdrop = memo(function Backdrop() {
  const { cities, stars } = useMemo(() => {
    const rand = mulberry32(20261017);
    const cityDots: { x: number; y: number; r: number; o: number; warm: boolean }[] = [];
    for (let c = 0; c < 38; c += 1) {
      const cx = rand() * W;
      const cy = 250 + rand() * (H - 230);
      const n = 6 + Math.floor(rand() * 34);
      const spread = 8 + rand() * 34;
      for (let i = 0; i < n; i += 1) {
        const ang = rand() * Math.PI * 2;
        const d = Math.pow(rand(), 1.6) * spread;
        const x = cx + Math.cos(ang) * d * 1.6;
        const y = cy + Math.sin(ang) * d * 0.7;
        if (Math.hypot(x - PLANET.cx, y - PLANET.cy) > PLANET.r - 6) continue;
        cityDots.push({ x, y, r: 0.6 + rand() * 1.5, o: 0.35 + rand() * 0.6, warm: rand() > 0.22 });
      }
    }
    const starDots = Array.from({ length: 90 }, () => ({ x: rand() * W, y: rand() * 230, r: rand() * 1.1 + 0.2, o: 0.2 + rand() * 0.6 }));
    return { cities: cityDots, stars: starDots.filter((s) => Math.hypot(s.x - PLANET.cx, s.y - PLANET.cy) > PLANET.r + 20) };
  }, []);

  return (
    <g>
      <defs>
        <radialGradient id="fs-space" cx="50%" cy="0%" r="90%">
          <stop offset="0%" stopColor="#0a1a33" />
          <stop offset="60%" stopColor="#040a16" />
          <stop offset="100%" stopColor="#02050c" />
        </radialGradient>
        <radialGradient id="fs-planet" cx="50%" cy="8%" r="60%">
          <stop offset="0%" stopColor="#123a5e" />
          <stop offset="35%" stopColor="#0b2541" />
          <stop offset="100%" stopColor="#040b17" />
        </radialGradient>
        <radialGradient id="fs-haze" cx="50%" cy="50%" r="50%">
          <stop offset="96%" stopColor="#37c2ff" stopOpacity="0" />
          <stop offset="98.6%" stopColor="#37c2ff" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#37c2ff" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="fs-depth" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#02050c" stopOpacity="0" />
          <stop offset="55%" stopColor="#02050c" stopOpacity="0.1" />
          <stop offset="100%" stopColor="#02050c" stopOpacity="0.75" />
        </linearGradient>
        <clipPath id="fs-planet-clip">
          <circle cx={PLANET.cx} cy={PLANET.cy} r={PLANET.r} />
        </clipPath>
        <filter id="fs-terrain" x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="0.0055 0.011" numOctaves="5" seed="7" result="n" />
          <feColorMatrix
            in="n"
            type="matrix"
            values="0 0 0 0 0.03  0 0 0 0 0.16  0 0 0 0 0.26  0 0 0 2.6 -1.05"
          />
        </filter>
        <filter id="fs-ridges" x="0" y="0" width="100%" height="100%">
          <feTurbulence type="turbulence" baseFrequency="0.018 0.03" numOctaves="3" seed="11" result="r" />
          <feColorMatrix in="r" type="matrix" values="0 0 0 0 0.25  0 0 0 0 0.55  0 0 0 0 0.75  0 0 0 1.4 -0.95" />
        </filter>
        <filter id="fs-clouds" x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="0.0028 0.006" numOctaves="4" seed="3" result="c" />
          <feColorMatrix in="c" type="matrix" values="0 0 0 0 0.85  0 0 0 0 0.9  0 0 0 0 1  0 0 0 3.2 -1.85" />
        </filter>
        <filter id="fs-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2.2" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <filter id="fs-limb" x="-10%" y="-10%" width="120%" height="120%">
          <feGaussianBlur stdDeviation="9" />
        </filter>
      </defs>

      <rect width={W} height={H} fill="url(#fs-space)" />
      {stars.map((s, i) => (
        <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="#cfe6ff" opacity={s.o} />
      ))}

      {/* Atmospheric limb glow along the planet's curvature. */}
      <circle cx={PLANET.cx} cy={PLANET.cy} r={PLANET.r + 26} fill="url(#fs-haze)" />
      <circle cx={PLANET.cx} cy={PLANET.cy} r={PLANET.r + 4} fill="none" stroke="#45c8ff" strokeOpacity="0.55" strokeWidth="10" filter="url(#fs-limb)" />

      <g clipPath="url(#fs-planet-clip)">
        <circle cx={PLANET.cx} cy={PLANET.cy} r={PLANET.r} fill="url(#fs-planet)" />
        <rect width={W} height={H} filter="url(#fs-terrain)" opacity="0.95" />
        <rect width={W} height={H} filter="url(#fs-ridges)" opacity="0.28" />
        {/* Faint graticule, curved with the planet. */}
        {[120, 260, 420, 600].map((d) => (
          <circle key={d} cx={PLANET.cx} cy={PLANET.cy} r={PLANET.r - d} fill="none" stroke="#2f7fb3" strokeOpacity="0.14" strokeWidth="1" />
        ))}
        {[-0.42, -0.28, -0.14, 0, 0.14, 0.28, 0.42].map((a) => (
          <line
            key={a}
            x1={PLANET.cx + Math.sin(a) * PLANET.r}
            y1={PLANET.cy - Math.cos(a) * PLANET.r}
            x2={PLANET.cx}
            y2={PLANET.cy}
            stroke="#2f7fb3"
            strokeOpacity="0.1"
            strokeWidth="1"
          />
        ))}
        <g filter="url(#fs-glow)">
          {cities.map((c, i) => (
            <circle key={i} cx={c.x} cy={c.y} r={c.r} fill={c.warm ? "#ffcf7a" : "#7fdcff"} opacity={c.o} />
          ))}
        </g>
        <rect width={W} height={H} filter="url(#fs-clouds)" opacity="0.32" />
        <rect width={W} height={H} fill="url(#fs-depth)" />
      </g>
    </g>
  );
});

/** Top-down airliner illustration, nose pointing up (−y), roughly 300 units long. */
function Airliner({ emergency }: { emergency: boolean }) {
  return (
    <g>
      <defs>
        <linearGradient id="fs-fuselage" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#7d8ba0" />
          <stop offset="45%" stopColor="#f4f7fb" />
          <stop offset="70%" stopColor="#dfe6ee" />
          <stop offset="100%" stopColor="#6f7d92" />
        </linearGradient>
        <linearGradient id="fs-wing" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#e6ecf3" />
          <stop offset="100%" stopColor="#8794a8" />
        </linearGradient>
        <linearGradient id="fs-engine" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#4c586a" />
          <stop offset="50%" stopColor="#c9d2dd" />
          <stop offset="100%" stopColor="#465265" />
        </linearGradient>
      </defs>
      {/* wings */}
      <path d="M-14 -18 L-158 52 L-160 66 L-150 70 L-16 36 Z" fill="url(#fs-wing)" stroke="#5b677a" strokeWidth="0.8" />
      <path d="M14 -18 L158 52 L160 66 L150 70 L16 36 Z" fill="url(#fs-wing)" stroke="#5b677a" strokeWidth="0.8" />
      {/* engines */}
      <rect x="-74" y="-6" width="18" height="40" rx="8" fill="url(#fs-engine)" />
      <rect x="56" y="-6" width="18" height="40" rx="8" fill="url(#fs-engine)" />
      <rect x="-72" y="-8" width="14" height="5" rx="2" fill="#1d2532" />
      <rect x="58" y="-8" width="14" height="5" rx="2" fill="#1d2532" />
      {/* horizontal stabilisers */}
      <path d="M-8 112 L-62 140 L-62 148 L-8 136 Z" fill="url(#fs-wing)" stroke="#5b677a" strokeWidth="0.8" />
      <path d="M8 112 L62 140 L62 148 L8 136 Z" fill="url(#fs-wing)" stroke="#5b677a" strokeWidth="0.8" />
      {/* fuselage */}
      <path d="M0 -158 C 12 -150 15 -128 15 -100 L15 120 C 15 140 8 156 0 162 C -8 156 -15 140 -15 120 L-15 -100 C -15 -128 -12 -150 0 -158 Z" fill="url(#fs-fuselage)" stroke="#55627a" strokeWidth="0.8" />
      {/* brand stripe and fin */}
      <path d="M0 -150 L0 150" stroke={emergency ? "#ff5a5f" : "#38c7ff"} strokeOpacity="0.55" strokeWidth="2.2" />
      <path d="M-2 108 L-2 160 L2 160 L2 108 Z" fill="#3d4a5e" />
      {/* cockpit windows */}
      <path d="M-9 -134 Q 0 -142 9 -134 L7 -128 Q 0 -133 -7 -128 Z" fill="#0d1a2c" />
      {/* navigation lights: red left, green right, white tail strobe */}
      <circle cx="-158" cy="60" r="3.2" fill="#ff3b45" className="fs-navlight" />
      <circle cx="158" cy="60" r="3.2" fill="#2bff8a" className="fs-navlight" />
      <circle cx="0" cy="162" r="2.6" fill="#ffffff" className="fs-strobe" />
    </g>
  );
}

export function FlightScene({
  samples,
  incidentAt,
  incidentLabel,
  emergency,
  focusIndex = null,
  actionLabel,
  callsignVisible = true,
  crop = "full",
}: {
  samples: SceneSample[];
  incidentAt?: string | null;
  incidentLabel?: string | null;
  emergency: boolean;
  /** Replay: place the aircraft at this sample instead of the latest one. */
  focusIndex?: number | null;
  actionLabel?: string | null;
  callsignVisible?: boolean;
  /** "band" frames the horizon-to-route strip for short, wide containers. */
  crop?: "full" | "band";
}) {
  const layout = useMemo(() => {
    const shown = samples.slice(-10);
    const times = shown.map((s) => new Date(s.at).getTime());
    const last = times.length ? times[times.length - 1] : 0;
    const span = Math.max(times.length ? last - times[0] : 0, 1000);
    // Past samples spread from 12% to 56% of the route by virtual time; the latest sits at 56%.
    const positions = times.map((t) => 0.56 - ((last - t) / span) * 0.44);
    const offset = samples.length - shown.length;
    return { shown, positions, offset };
  }, [samples]);

  const { shown, positions, offset } = layout;
  const focus = focusIndex !== null && focusIndex - offset >= 0 && focusIndex - offset < shown.length ? focusIndex - offset : shown.length - 1;
  const aircraftF = shown.length ? positions[focus] : 0.56;
  const aircraft = pointAt(aircraftF);
  const current = shown.length ? shown[focus].telemetry : null;

  // Incident zone: the last sample committed at or before the incident.
  let incidentF: number | null = null;
  if (incidentAt && shown.length) {
    const it = new Date(incidentAt).getTime();
    let idx = -1;
    shown.forEach((s, i) => {
      if (new Date(s.at).getTime() <= it) idx = i;
    });
    incidentF = idx >= 0 ? positions[idx] : positions[0];
  }
  const incident = incidentF !== null ? pointAt(incidentF) : null;
  // Tag goes up-left of the aircraft so it never sits under the right-hand overlay column.
  const labelLeft = aircraft.x > W * 0.35;

  return (
    <svg className={`scene ${emergency ? "scene--emergency" : ""}`} viewBox={crop === "band" ? `0 170 ${W} 520` : `0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" role="img"
      aria-label={`Synthetic flight scene: ${shown.length} telemetry samples on an illustrative route${incident ? `; incident zone at ${formatClock(incidentAt)}` : ""}${emergency ? "; emergency state" : ""}`}>
      <defs>
        <filter id="fs-route-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="4" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <filter id="fs-shadow" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="10" />
        </filter>
        <radialGradient id="fs-red" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ff3b45" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#ff3b45" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="fs-vignette" cx="50%" cy="50%" r="75%">
          <stop offset="60%" stopColor="#ff1f2d" stopOpacity="0" />
          <stop offset="100%" stopColor="#ff1f2d" stopOpacity="0.28" />
        </radialGradient>
      </defs>

      <Backdrop />

      {/* Route: travelled segment glows cyan; the remainder is a faint dashed projection. */}
      <path d={pathBetween(0.02, 1)} className="scene__route-ahead" />
      {shown.length > 0 && <path d={pathBetween(Math.min(positions[0], aircraftF), aircraftF)} className="scene__route-flown" filter="url(#fs-route-glow)" />}
      {incident && incidentF !== null && incidentF < aircraftF && <path d={pathBetween(incidentF, aircraftF)} className="scene__route-incident" />}

      {/* Waypoints = real telemetry samples, labelled with their virtual time. */}
      {shown.map((s, i) => {
        if (i === focus) return null;
        const p = pointAt(positions[i]);
        const future = i > focus;
        const labelled = shown.length <= 6 || i % 2 === (shown.length - 1) % 2;
        return (
          <g key={s.at + i} className={`scene__wp ${future ? "scene__wp--future" : ""}`}>
            <circle cx={p.x} cy={p.y} r={7} className="scene__wp-ring" />
            <circle cx={p.x} cy={p.y} r={3} className="scene__wp-dot" />
            {labelled && (
              <text x={p.x} y={p.y + 26} textAnchor="middle" className="scene__wp-label">
                WP{offset + i + 1} · {formatClock(s.at)}
              </text>
            )}
          </g>
        );
      })}

      {/* Incident zone. */}
      {incident && (
        <g className="scene__incident">
          <circle cx={incident.x} cy={incident.y} r={120} fill="url(#fs-red)" />
          <circle cx={incident.x} cy={incident.y} r={58} className="scene__incident-ring scene__incident-ring--a" />
          <circle cx={incident.x} cy={incident.y} r={34} className="scene__incident-ring scene__incident-ring--b" />
          <path d={`M${incident.x} ${incident.y - 16} L${incident.x + 15} ${incident.y + 11} L${incident.x - 15} ${incident.y + 11} Z`} className="scene__incident-tri" />
          <text x={incident.x} y={incident.y + 7} textAnchor="middle" className="scene__incident-bang">!</text>
          <g transform={`translate(${incident.x - 300} ${incident.y - 100})`}>
            <rect width="282" height="56" rx="4" className="scene__incident-box" />
            <text x="14" y="24" className="scene__incident-title">INCIDENT ZONE</text>
            <text x="14" y="43" className="scene__incident-sub">
              {(incidentLabel ?? "Guardian incident").slice(0, 26)} · {formatClock(incidentAt)}
            </text>
          </g>
        </g>
      )}

      {/* Aircraft: ground shadow for depth, then the illustration, foreshortened for an oblique view. */}
      {current && (
        <g className="scene__aircraft" style={{ transform: `translate(${aircraft.x}px, ${aircraft.y}px)` }}>
          <g transform={`translate(70 86) scale(0.7) rotate(${aircraft.angle + 90})`} opacity="0.5" filter="url(#fs-shadow)">
            <path d="M0 -158 L15 -100 L158 52 L150 70 L15 40 L15 120 L62 140 L62 148 L8 140 L0 162 L-8 140 L-62 148 L-62 140 L-15 120 L-15 40 L-150 70 L-158 52 L-15 -100 Z" fill="#000" />
          </g>
          <g transform={`scale(0.8) rotate(${aircraft.angle + 90})`}>
            <Airliner emergency={emergency} />
          </g>
          {emergency && <circle r={150} fill="url(#fs-red)" className="scene__aircraft-alert" />}
        </g>
      )}

      {/* Callsign tag with leader line, as in the reference flight deck. */}
      {current && callsignVisible && (
        <g className="scene__tag">
          <line x1={aircraft.x} y1={aircraft.y - 20} x2={labelLeft ? aircraft.x - 150 : aircraft.x + 150} y2={aircraft.y - 120} />
          <g transform={`translate(${labelLeft ? aircraft.x - 150 - 230 : aircraft.x + 150} ${aircraft.y - 160})`}>
            <rect width="230" height="58" rx="4" className={`scene__tag-box ${emergency ? "scene__tag-box--alert" : ""}`} />
            <circle cx="18" cy="21" r="5" className={emergency ? "scene__tag-dot--alert" : "scene__tag-dot"} />
            <text x="32" y="26" className="scene__tag-call">{current.aircraft_id}</text>
            <text x="18" y="46" className="scene__tag-data">
              {formatFlightLevel(current.altitude_ft)} · {formatNumber(current.airspeed_kts)} KT · {humanize(current.flight_phase).toUpperCase()}
            </text>
          </g>
        </g>
      )}

      {actionLabel && (
        <text x={W / 2} y={H - 64} textAnchor="middle" className="scene__action">
          {actionLabel}
        </text>
      )}
      {emergency && <rect width={W} height={H} fill="url(#fs-vignette)" pointerEvents="none" />}
    </svg>
  );
}
