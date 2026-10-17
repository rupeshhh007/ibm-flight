import { Empty } from "../components/ui";
import { useAeroGuard } from "../hooks/useAeroGuard";

export function VisionPage() {
  const { snapshot } = useAeroGuard();

  const pilot1 = snapshot?.pilots.find((p) => p.pilot_id === "PILOT_1");
  const pilot2 = snapshot?.pilots.find((p) => p.pilot_id === "PILOT_2");

  const obs1 = pilot1?.latest_observation;
  const obs2 = pilot2?.latest_observation;

  const isResp1 = obs1 ? obs1.observation_status === "RESPONSIVE" : true;
  const isResp2 = obs2 ? obs2.observation_status === "RESPONSIVE" : true;

  const conf1 = obs1 ? obs1.observation_quality.toFixed(2) : "0.71";
  const conf2 = obs2 ? obs2.observation_quality.toFixed(2) : "0.69";

  if (!snapshot) return <Empty>Loading Vision Analysis module…</Empty>;

  return (
    <div className="vision-page-layout">
      {/* Top Header */}
      <div className="vision-header-strip">
        <div className="vision-title-group">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#38bdf8" strokeWidth="2">
            <path d="M23 7l-7 5 7 5V7z" />
            <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
          </svg>
          <h2 className="vision-header-title">VISION ANALYSIS</h2>
        </div>
        <div className="vision-active-badge">
          <span className="badge-pulse" />
          <span className="mono">2 CAMERAS ACTIVE · 30 FPS</span>
        </div>
      </div>

      <div className="vision-main-grid">
        {/* Dual Camera Feeds Container */}
        <div className="vision-cameras-container">
          {/* Pilot 1 Camera Feed */}
          <div className="vision-feed-box">
            <div className="feed-box-top">
              <span className="feed-name">PILOT 1 CAMERA</span>
              <div className="feed-badges">
                <span className="badge-chip">Live Analysis</span>
                <span className={`badge-chip ${isResp1 ? "badge--green" : "badge--red"}`}>
                  {isResp1 ? "Responsive" : "No Response"}
                </span>
              </div>
            </div>

            <div className="feed-view-screen">
              <svg viewBox="0 0 320 200" className="camera-view-svg">
                {/* Cockpit interior mock */}
                <rect width="320" height="200" fill="#0f172a" />
                <path d="M 20 20 Q 160 5 300 20 L 310 100 L 10 100 Z" fill="#070c18" opacity="0.6" />
                {/* Seat and Headrest */}
                <rect x="110" y="55" width="100" height="90" rx="14" fill="#1e293b" stroke="#334155" strokeWidth="1.5" />
                {/* Pilot Silhouette */}
                <ellipse cx="160" cy="100" rx="34" ry="40" fill="#090d16" stroke="#334155" strokeWidth="2" />

                {/* AI Facial Tracking HUD */}
                <rect
                  x="125"
                  y="65"
                  width="70"
                  height="75"
                  fill="none"
                  stroke={isResp1 ? "#10b981" : "#ef4444"}
                  strokeWidth="1.5"
                  strokeDasharray="4 2"
                />
                {/* Corner brackets */}
                <path d="M 120 75 L 120 60 L 135 60" fill="none" stroke={isResp1 ? "#10b981" : "#ef4444"} strokeWidth="2" />
                <path d="M 185 60 L 200 60 L 200 75" fill="none" stroke={isResp1 ? "#10b981" : "#ef4444"} strokeWidth="2" />
                <path d="M 120 130 L 120 145 L 135 145" fill="none" stroke={isResp1 ? "#10b981" : "#ef4444"} strokeWidth="2" />
                <path d="M 185 145 L 200 145 L 200 130" fill="none" stroke={isResp1 ? "#10b981" : "#ef4444"} strokeWidth="2" />

                {/* Eye landmark points */}
                <circle cx="145" cy="92" r="2.5" fill={isResp1 ? "#10b981" : "#ef4444"} />
                <circle cx="175" cy="92" r="2.5" fill={isResp1 ? "#10b981" : "#ef4444"} />
                <circle cx="160" cy="105" r="2" fill="#38bdf8" />
                <line x1="150" y1="120" x2="170" y2="120" stroke={isResp1 ? "#10b981" : "#ef4444"} strokeWidth="2" />

                {/* Target reticle */}
                <circle cx="160" cy="100" r="48" fill="none" stroke="rgba(56, 189, 248, 0.15)" strokeDasharray="3 3" />
              </svg>
            </div>

            <div className="feed-bottom-meter">
              <span className="meter-label">Confidence</span>
              <svg viewBox="0 0 160 20" className="feed-meter-wave">
                <polyline
                  points="0,10 20,10 30,10 35,3 40,17 45,5 50,12 70,10 85,10 90,3 95,17 100,5 110,10 160,10"
                  fill="none"
                  stroke={isResp1 ? "#10b981" : "#ef4444"}
                  strokeWidth="1.5"
                />
              </svg>
              <span className="meter-val mono">{conf1}</span>
            </div>
          </div>

          {/* Pilot 2 Camera Feed */}
          <div className="vision-feed-box">
            <div className="feed-box-top">
              <span className="feed-name">PILOT 2 CAMERA</span>
              <div className="feed-badges">
                <span className="badge-chip">Live Analysis</span>
                <span className={`badge-chip ${isResp2 ? "badge--green" : "badge--red"}`}>
                  {isResp2 ? "Responsive" : "No Response"}
                </span>
              </div>
            </div>

            <div className="feed-view-screen">
              <svg viewBox="0 0 320 200" className="camera-view-svg">
                {/* Cockpit interior mock */}
                <rect width="320" height="200" fill="#0f172a" />
                <path d="M 20 20 Q 160 5 300 20 L 310 100 L 10 100 Z" fill="#070c18" opacity="0.6" />
                {/* Seat and Headrest */}
                <rect x="110" y="55" width="100" height="90" rx="14" fill="#1e293b" stroke="#334155" strokeWidth="1.5" />
                {/* Pilot Silhouette */}
                <ellipse cx="160" cy="100" rx="34" ry="40" fill="#090d16" stroke="#334155" strokeWidth="2" />

                {/* AI Facial Tracking HUD */}
                <rect
                  x="125"
                  y="65"
                  width="70"
                  height="75"
                  fill="none"
                  stroke={isResp2 ? "#10b981" : "#ef4444"}
                  strokeWidth="1.5"
                  strokeDasharray="4 2"
                />
                {/* Corner brackets */}
                <path d="M 120 75 L 120 60 L 135 60" fill="none" stroke={isResp2 ? "#10b981" : "#ef4444"} strokeWidth="2" />
                <path d="M 185 60 L 200 60 L 200 75" fill="none" stroke={isResp2 ? "#10b981" : "#ef4444"} strokeWidth="2" />
                <path d="M 120 130 L 120 145 L 135 145" fill="none" stroke={isResp2 ? "#10b981" : "#ef4444"} strokeWidth="2" />
                <path d="M 185 145 L 200 145 L 200 130" fill="none" stroke={isResp2 ? "#10b981" : "#ef4444"} strokeWidth="2" />

                {/* Eye landmark points */}
                <circle cx="145" cy="92" r="2.5" fill={isResp2 ? "#10b981" : "#ef4444"} />
                <circle cx="175" cy="92" r="2.5" fill={isResp2 ? "#10b981" : "#ef4444"} />
                <circle cx="160" cy="105" r="2" fill="#38bdf8" />
                <line x1="150" y1="120" x2="170" y2="120" stroke={isResp2 ? "#10b981" : "#ef4444"} strokeWidth="2" />

                {/* Target reticle */}
                <circle cx="160" cy="100" r="48" fill="none" stroke="rgba(56, 189, 248, 0.15)" strokeDasharray="3 3" />
              </svg>
            </div>

            <div className="feed-bottom-meter">
              <span className="meter-label">Confidence</span>
              <svg viewBox="0 0 160 20" className="feed-meter-wave">
                <polyline
                  points="0,10 20,10 30,10 35,3 40,17 45,5 50,12 70,10 85,10 90,3 95,17 100,5 110,10 160,10"
                  fill="none"
                  stroke={isResp2 ? "#10b981" : "#ef4444"}
                  strokeWidth="1.5"
                />
              </svg>
              <span className="meter-val mono">{conf2}</span>
            </div>
          </div>
        </div>

        {/* Right Column: Detection Metrics & Frame Analysis */}
        <div className="vision-metrics-sidebar">
          {/* Detection Metrics */}
          <div className="cyber-card">
            <div className="cyber-card-header">
              <span className="cyber-card-title">DETECTION METRICS</span>
            </div>
            <div className="metrics-list">
              <div className="metric-item">
                <span className="metric-name">Face Detection</span>
                <span className="metric-score mono text-ok">0.96</span>
              </div>
              <div className="metric-item">
                <span className="metric-name">Head Pose Stability</span>
                <span className="metric-score mono text-cyan">0.12</span>
              </div>
              <div className="metric-item">
                <span className="metric-name">Eye Activity (PERCLOS)</span>
                <span className="metric-score mono text-alert">0.08</span>
              </div>
              <div className="metric-item">
                <span className="metric-name">Body Movement</span>
                <span className="metric-score mono text-alert">0.05</span>
              </div>
            </div>
          </div>

          {/* Frame Analysis Summary */}
          <div className="cyber-card">
            <div className="cyber-card-header">
              <span className="cyber-card-title">FRAME ANALYSIS</span>
            </div>
            <div className="metrics-list">
              <div className="metric-item">
                <span className="metric-name">Unknown</span>
                <span className="metric-score mono">0</span>
              </div>
              <div className="metric-item">
                <span className="metric-name">Obstructed</span>
                <span className="metric-score mono">0</span>
              </div>
              <div className="metric-item">
                <span className="metric-name">Poor Quality</span>
                <span className="metric-score mono">0</span>
              </div>
              <div className="metric-item">
                <span className="metric-name">Valid Observations</span>
                <span className="metric-score mono text-ok">4</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
