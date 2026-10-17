import type { AircraftTelemetry } from "../api/types";
import { formatNumber, humanize } from "./format";
import { Empty } from "./ui";

const W = 640;
const H = 300;
const PAD = 40;

/**
 * Simple 2D plot of the synthetic track (lat/lon from TELEMETRY_UPDATED events
 * of the current run). A demonstration placeholder — not a navigation display.
 */
export function FlightDisplay({ track, actionLabel }: { track: AircraftTelemetry[]; actionLabel?: string | null }) {
  if (track.length === 0) return <Empty>No synthetic telemetry for this run yet.</Empty>;

  const lats = track.map((t) => t.latitude);
  const lons = track.map((t) => t.longitude);
  // Keep a minimum span so a stationary or single-point track still renders centred.
  const span = Math.max(Math.max(...lats) - Math.min(...lats), Math.max(...lons) - Math.min(...lons), 0.02);
  const midLat = (Math.max(...lats) + Math.min(...lats)) / 2;
  const midLon = (Math.max(...lons) + Math.min(...lons)) / 2;
  const scale = Math.min(W - PAD * 2, H - PAD * 2) / span;
  const project = (t: AircraftTelemetry) => ({
    x: W / 2 + (t.longitude - midLon) * scale,
    y: H / 2 - (t.latitude - midLat) * scale,
  });

  const points = track.map(project);
  const last = track[track.length - 1];
  const head = points[points.length - 1];

  return (
    <figure className="flight">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Synthetic track with ${track.length} positions; heading ${Math.round(last.heading_deg)} degrees`}>
        <defs>
          <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M32 0 L0 0 0 32" className="flight__grid" />
          </pattern>
        </defs>
        <rect width={W} height={H} fill="url(#grid)" />
        <circle cx={W / 2} cy={H / 2} r={110} className="flight__range" />
        <circle cx={W / 2} cy={H / 2} r={55} className="flight__range" />
        {points.length > 1 && <polyline points={points.map((p) => `${p.x},${p.y}`).join(" ")} className="flight__track" />}
        {points.slice(0, -1).map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={2.5} className="flight__dot" />
        ))}
        <g transform={`translate(${head.x} ${head.y}) rotate(${last.heading_deg})`} className="flight__aircraft">
          <path d="M0 -14 L3 -3 L13 3 L13 6 L3 3 L2 10 L6 13 L6 15 L0 13 L-6 15 L-6 13 L-2 10 L-3 3 L-13 6 L-13 3 L-3 -3 Z" />
        </g>
        <text x={14} y={24} className="flight__hud">ALT {formatNumber(last.altitude_ft)} FT</text>
        <text x={14} y={44} className="flight__hud">IAS {formatNumber(last.airspeed_kts)} KT</text>
        <text x={W - 14} y={24} textAnchor="end" className="flight__hud">HDG {formatNumber(last.heading_deg).padStart(3, "0")}°</text>
        <text x={W - 14} y={44} textAnchor="end" className="flight__hud">{humanize(last.flight_phase).toUpperCase()}</text>
        {actionLabel && (
          <text x={W / 2} y={H - 16} textAnchor="middle" className="flight__action">
            SYMBOLIC ACTION: {actionLabel}
          </text>
        )}
      </svg>
      <figcaption className="meta">Synthetic positions only · placeholder display · not for navigation</figcaption>
    </figure>
  );
}
