import type { PilotSnapshot } from "../api/types";
import { formatVirtualTime } from "./format";

interface CockpitCameraFeedProps {
  pilot: PilotSnapshot;
  role: "Captain" | "First Officer";
  onAcknowledge?: () => void;
  ackDisabled?: boolean;
}

export function CockpitCameraFeed({ pilot, role, onAcknowledge, ackDisabled }: CockpitCameraFeedProps) {
  const obs = pilot.latest_observation;
  const isResponsive = obs ? obs.observation_status === "RESPONSIVE" : true;
  const isPossiblyUnresponsive = obs?.observation_status === "POSSIBLY_UNRESPONSIVE";
  const isUnknown = obs?.observation_status === "UNKNOWN";

  const statusLabel = obs ? (isResponsive ? "RESPONSIVE" : isPossiblyUnresponsive ? "NO RESPONSE" : isUnknown ? "UNKNOWN" : "STANDBY") : "STANDBY";
  const statusColorClass = isResponsive ? "status--green" : isPossiblyUnresponsive ? "status--red" : "status--amber";
  const confidence = obs ? obs.observation_quality.toFixed(2) : "0.93";
  const lastInteraction = obs ? formatVirtualTime(obs.observed_at) : "00:07:28";

  return (
    <div className={`cockpit-camera-card ${isPossiblyUnresponsive ? "is-alert" : ""}`}>
      <div className="cockpit-camera-header">
        <div className="cockpit-pilot-id">
          <span className="pilot-dot" />
          <span className="pilot-name">
            {pilot.pilot_id === "PILOT_1" ? "PILOT 1" : "PILOT 2"} ({role})
          </span>
        </div>
        <div className={`camera-status-badge ${statusColorClass}`}>
          <span className="badge-pulse" />
          <span>{statusLabel}</span>
        </div>
      </div>

      <div className="cockpit-camera-viewport">
        {/* SVG Cockpit Interior & AI Face Detection HUD */}
        <svg viewBox="0 0 280 150" className="cockpit-hud-svg" aria-label={`Cockpit view of ${role}`}>
          <defs>
            <linearGradient id="cockpitBg" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1e293b" />
              <stop offset="100%" stopColor="#0f172a" />
            </linearGradient>
            <linearGradient id="seatGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#334155" />
              <stop offset="100%" stopColor="#1e293b" />
            </linearGradient>
          </defs>

          {/* Background cockpit cabin & seat */}
          <rect width="280" height="150" fill="url(#cockpitBg)" />
          
          {/* Cockpit window curve */}
          <path d="M 10 15 Q 140 5 270 15 L 275 60 L 5 60 Z" fill="#090d16" opacity="0.6" />
          <path d="M 30 20 L 250 20" stroke="rgba(56, 189, 248, 0.2)" strokeWidth="1" strokeDasharray="4 4" />

          {/* Seat Headrest and pilot silhouette */}
          <rect x="95" y="45" width="90" height="70" rx="16" fill="url(#seatGrad)" stroke="#475569" strokeWidth="1.5" />
          <path d="M 80 115 C 80 95, 200 95, 200 115 L 210 150 L 70 150 Z" fill="#334155" opacity="0.8" />

          {/* Pilot head silhouette */}
          <ellipse cx="140" cy="80" rx="28" ry="32" fill="#1e293b" stroke="#334155" strokeWidth="2" />

          {/* AI Face Detection Bounding Box */}
          {(!obs || obs.face_visible) && (
            <g className="hud-target">
              <rect
                x="108"
                y="48"
                width="64"
                height="70"
                fill="none"
                stroke={isPossiblyUnresponsive ? "#ef4444" : "#10b981"}
                strokeWidth="1.5"
                strokeDasharray="4 2"
              />
              {/* Corner brackets */}
              <path d="M 104 56 L 104 44 L 116 44" fill="none" stroke={isPossiblyUnresponsive ? "#ef4444" : "#10b981"} strokeWidth="2.5" />
              <path d="M 164 44 L 176 44 L 176 56" fill="none" stroke={isPossiblyUnresponsive ? "#ef4444" : "#10b981"} strokeWidth="2.5" />
              <path d="M 104 110 L 104 122 L 116 122" fill="none" stroke={isPossiblyUnresponsive ? "#ef4444" : "#10b981"} strokeWidth="2.5" />
              <path d="M 164 122 L 176 122 L 176 110" fill="none" stroke={isPossiblyUnresponsive ? "#ef4444" : "#10b981"} strokeWidth="2.5" />

              {/* Facial landmark points */}
              <circle cx="128" cy="72" r="2" fill={isPossiblyUnresponsive ? "#ef4444" : "#38bdf8"} />
              <circle cx="152" cy="72" r="2" fill={isPossiblyUnresponsive ? "#ef4444" : "#38bdf8"} />
              <circle cx="140" cy="85" r="1.5" fill={isPossiblyUnresponsive ? "#ef4444" : "#38bdf8"} />
              <line x1="134" y1="96" x2="146" y2="96" stroke={isPossiblyUnresponsive ? "#ef4444" : "#38bdf8"} strokeWidth="1.5" />
            </g>
          )}

          {/* Camera timestamp & frame info */}
          <text x="10" y="20" fill="rgba(255,255,255,0.4)" fontSize="9" fontFamily="monospace">CAM-0{pilot.pilot_id === "PILOT_1" ? "1" : "2"} · 30 FPS</text>
          <text x="270" y="20" textAnchor="end" fill="rgba(56, 189, 248, 0.7)" fontSize="9" fontFamily="monospace">LIVE</text>
        </svg>

        {/* Live Audio / ECG Pulse wave line */}
        <div className="cockpit-wave-bar">
          <svg viewBox="0 0 160 24" className="ecg-waveform" preserveAspectRatio="none">
            <polyline
              points="0,12 20,12 30,12 35,4 40,20 45,6 50,14 55,12 75,12 85,12 90,4 95,20 100,6 105,14 110,12 160,12"
              fill="none"
              stroke={isPossiblyUnresponsive ? "#ef4444" : "#10b981"}
              strokeWidth="1.5"
            />
          </svg>
        </div>
      </div>

      <div className="cockpit-camera-meta">
        <div className="meta-stat">
          <span className="stat-label">Confidence</span>
          <span className="stat-value mono">{confidence}</span>
        </div>
        <div className="meta-stat">
          <span className="stat-label">Last Interaction</span>
          <span className="stat-value mono">{lastInteraction}</span>
        </div>
      </div>

      {onAcknowledge && (
        <button
          type="button"
          className="btn btn--small btn--primary ack-btn"
          disabled={ackDisabled}
          onClick={onAcknowledge}
        >
          Acknowledge as {pilot.pilot_id === "PILOT_1" ? "Pilot 1" : "Pilot 2"}
        </button>
      )}
    </div>
  );
}
