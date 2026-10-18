import { useEffect, useState } from "react";
import { Chip, TelemetryStrip } from "./components/console";
import { formatClock, humanize } from "./components/format";
import { Icon, type IconName } from "./components/icons";
import { OutcomeBanner } from "./components/OutcomeBanner";
import { GUARDIAN_TONE, SENTINEL_TONE, type Tone } from "./components/tones";
import { Notice } from "./components/ui";
import { useAeroGuard } from "./hooks/useAeroGuard";
import { BlackBoxPage } from "./pages/BlackBoxPage";
import { FlightDeckPage } from "./pages/FlightDeckPage";
import { GuardianPage } from "./pages/GuardianPage";
import { ScenariosPage } from "./pages/ScenariosPage";
import { SentinelPage } from "./pages/SentinelPage";
import { VisionPage } from "./pages/VisionPage";

const VIEWS = [
  { id: "flightdeck", label: "Flight Deck", icon: "deck", Page: FlightDeckPage },
  { id: "guardian", label: "Guardian", icon: "shield", Page: GuardianPage },
  { id: "sentinel", label: "Sentinel", icon: "tower", Page: SentinelPage },
  { id: "vision", label: "Vision", icon: "vision", Page: VisionPage },
  { id: "blackbox", label: "Black Box", icon: "blackbox", Page: BlackBoxPage },
  { id: "scenarios", label: "Scenarios", icon: "scenario", Page: ScenariosPage },
] as const satisfies readonly { id: string; label: string; icon: IconName; Page: () => JSX.Element }[];
type ViewId = (typeof VIEWS)[number]["id"];

// Older links keep working: #cockpit/#deck → Flight Deck, #atc → Sentinel (fictional ATC), #simulation → Scenarios.
const ALIASES: Record<string, ViewId> = {
  cockpit: "flightdeck",
  deck: "flightdeck",
  "flight-deck": "flightdeck",
  atc: "sentinel",
  simulation: "scenarios",
  simulator: "scenarios",
};

function viewFromHash(): ViewId {
  const id = window.location.hash.replace("#", "").toLowerCase();
  if (VIEWS.some((v) => v.id === id)) return id as ViewId;
  return ALIASES[id] ?? "flightdeck";
}

export const SIMULATION_NOTICE = "SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE";

export function App() {
  const [view, setView] = useState<ViewId>(viewFromHash);
  const { snapshot, connection, syncError, lastSyncAt, pending, outcome, dismissOutcome } = useAeroGuard();

  useEffect(() => {
    const onHash = () => setView(viewFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const active = VIEWS.find((v) => v.id === view) ?? VIEWS[0];
  const connectionTone: Tone = connection === "online" ? (syncError ? "warn" : "ok") : connection === "offline" ? "alert" : "muted";
  const connectionLabel = connection === "online" ? (syncError ? "Backend degraded" : "Backend online") : connection === "offline" ? "Backend offline" : "Connecting…";
  // Run state is derived only from backend state; nothing is assumed before a snapshot exists.
  const runState: { tone: Tone; label: string } = !snapshot
    ? { tone: "muted", label: connection === "connecting" ? "Waiting for state…" : "State unavailable" }
    : snapshot.scenario_run_id
      ? { tone: snapshot.active_incident ? "alert" : "ok", label: snapshot.active_incident ? "Incident active" : "Running" }
      : { tone: "muted", label: "Idle" };

  const attention: Partial<Record<ViewId, string>> = {
    flightdeck: snapshot?.active_incident ? "Active incident" : undefined,
    guardian: snapshot?.active_incident ? "Active incident" : undefined,
    sentinel: snapshot?.sentinel_state === "AWAITING_ATC" && snapshot.active_incident ? "Decision required" : undefined,
  };

  return (
    <div className={`shell ${snapshot?.active_incident ? "shell--emergency" : ""}`}>
      <div className="safety-strip" role="note">
        <Icon name="alert" size={14} />
        <span>{SIMULATION_NOTICE}</span>
      </div>

      <header className="masthead">
        <a className="brand" href="#flightdeck" aria-label="AeroGuard Flight Deck">
          <svg viewBox="0 0 40 40" className="brand__mark" aria-hidden="true">
            <path d="M20 3 L35 9 V20 C35 28.6 28.8 35.2 20 37 C11.2 35.2 5 28.6 5 20 V9 Z" className="brand__shield" />
            <path d="M20 11 L21.8 17.6 L28.5 19.6 L21.8 21.6 L20 28.5 L18.2 21.6 L11.5 19.6 L18.2 17.6 Z" className="brand__star" />
          </svg>
          <span className="brand__text">
            <span className="brand__name">AeroGuard</span>
            <span className="brand__tag">Flight safety simulation</span>
          </span>
        </a>

        <nav className="tabs" aria-label="Views">
          {VIEWS.map((v) => (
            <a
              key={v.id}
              href={`#${v.id}`}
              className={`tabs__tab ${view === v.id ? "is-active" : ""}`}
              aria-current={view === v.id ? "page" : undefined}
              aria-label={attention[v.id] ? `${v.label} (${attention[v.id]})` : v.label}
            >
              <Icon name={v.icon} size={15} />
              <span className="tabs__label">{v.label}</span>
              {attention[v.id] && <span className="tabs__alert" aria-hidden="true" />}
            </a>
          ))}
        </nav>

        <div className="masthead__status" aria-label="System status">
          <span className="simclock mono">
            <span className="sr-only">Simulation time</span>SIM {formatClock(snapshot?.virtual_time)}
          </span>
          <Chip tone={runState.tone} live={runState.tone === "alert"}>
            {runState.label}
          </Chip>
          <Chip tone={connectionTone} live={connection === "connecting"}>
            {connectionLabel}
          </Chip>
        </div>
      </header>

      <div className="subbar">
        {view !== "flightdeck" && <TelemetryStrip snapshot={snapshot} />}
        <div className="subbar__states">
          {snapshot ? (
            <>
              <Chip tone={GUARDIAN_TONE[snapshot.guardian_state]}>Guardian {humanize(snapshot.guardian_state)}</Chip>
              <Chip tone={SENTINEL_TONE[snapshot.sentinel_state]}>Sentinel {humanize(snapshot.sentinel_state)}</Chip>
            </>
          ) : (
            <span className="muted-text">Waiting for state…</span>
          )}
        </div>
      </div>

      <div className="notices">
        {connection === "offline" && (
          <Notice tone="alert" title="Backend unreachable." live>
            Start it with <code>make backend</code> (127.0.0.1:8000). Showing the last confirmed data
            {lastSyncAt ? ` from ${new Date(lastSyncAt).toLocaleTimeString()}` : ""}; retrying automatically.
          </Notice>
        )}
        {connection === "online" && syncError && (
          <Notice tone="warn" title="Sync problem." live>
            {syncError}
          </Notice>
        )}
        <OutcomeBanner pending={pending} outcome={outcome} onDismiss={dismissOutcome} />
      </div>

      <main className="main" aria-label={active.label}>
        <active.Page />
      </main>

      <footer className="footer">
        <span className="footer__notice">{SIMULATION_NOTICE}</span>
        <span>Synthetic telemetry · deterministic scenarios · illustrative scenery · no real aircraft, avionics or ATC</span>
      </footer>
    </div>
  );
}
