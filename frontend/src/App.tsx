import { useEffect, useState } from "react";
import { OutcomeBanner } from "./components/OutcomeBanner";
import { formatVirtualTime, humanize, shortId } from "./components/format";
import { GUARDIAN_TONE, SENTINEL_TONE } from "./components/tones";
import { Pill } from "./components/ui";
import { useAeroGuard } from "./hooks/useAeroGuard";
import { ATCPage } from "./pages/ATCPage";
import { CockpitPage } from "./pages/CockpitPage";
import { SimulationPage } from "./pages/SimulationPage";

const TABS = [
  { id: "cockpit", label: "Cockpit Monitoring", Page: CockpitPage },
  { id: "atc", label: "Fictional ATC", Page: ATCPage },
  { id: "simulation", label: "Emergency Simulation", Page: SimulationPage },
] as const;
type TabId = (typeof TABS)[number]["id"];

// Hash-based tabs (#cockpit, #atc, #simulation): no router dependency, and a
// reload or shared link keeps the same screen.
function tabFromHash(): TabId {
  const id = window.location.hash.replace("#", "");
  return TABS.some((t) => t.id === id) ? (id as TabId) : "simulation";
}

export const SIMULATION_NOTICE = "SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE";

export function App() {
  const [tab, setTab] = useState<TabId>(tabFromHash);
  const { snapshot, connection, syncError, lastSyncAt, pending, outcome, dismissOutcome } = useAeroGuard();

  useEffect(() => {
    const onHash = () => setTab(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const active = TABS.find((t) => t.id === tab) ?? TABS[2];
  const connectionTone = connection === "online" ? (syncError ? "warn" : "ok") : connection === "offline" ? "alert" : "muted";

  return (
    <div className="app">
      <div className="sim-banner" role="note">
        {SIMULATION_NOTICE}
      </div>

      <header className="topbar">
        <div className="brand">
          <svg viewBox="0 0 32 32" className="brand__mark" aria-hidden="true">
            <path d="M16 3 L27 8 V16 C27 22.5 22.4 27.4 16 29 C9.6 27.4 5 22.5 5 16 V8 Z" />
            <path d="M16 10 L17.6 15 L23 16.5 L17.6 18 L16 23 L14.4 18 L9 16.5 L14.4 15 Z" className="brand__plane" />
          </svg>
          <div>
            <h1 className="brand__name">AeroGuard</h1>
            <p className="brand__tag">Cockpit monitoring & emergency-response simulation</p>
          </div>
        </div>

        <div className="topbar__status" aria-label="System status">
          <Pill tone={connectionTone} pulse={connection === "connecting"}>
            Backend {connection === "online" ? (syncError ? "degraded" : "online") : connection}
          </Pill>
          {snapshot && (
            <>
              <Pill tone={GUARDIAN_TONE[snapshot.guardian_state]}>Guardian {humanize(snapshot.guardian_state)}</Pill>
              <Pill tone={SENTINEL_TONE[snapshot.sentinel_state]}>Sentinel {humanize(snapshot.sentinel_state)}</Pill>
              <span className="topbar__run mono" title={snapshot.scenario_run_id ?? undefined}>
                {snapshot.scenario_id ?? "no scenario"} · run {shortId(snapshot.scenario_run_id)} · T {formatVirtualTime(snapshot.virtual_time)}
              </span>
            </>
          )}
        </div>
      </header>

      <nav className="tabs" role="tablist" aria-label="Screens">
        {TABS.map((t) => (
          <a
            key={t.id}
            href={`#${t.id}`}
            role="tab"
            aria-selected={tab === t.id}
            className={`tabs__tab ${tab === t.id ? "is-active" : ""}`}
          >
            {t.label}
            {t.id === "atc" && snapshot?.sentinel_state === "AWAITING_ATC" && <span className="tabs__badge" aria-label="Decision required" />}
            {t.id === "cockpit" && snapshot?.active_incident && <span className="tabs__badge" aria-label="Active incident" />}
          </a>
        ))}
      </nav>

      {connection === "offline" && (
        <div className="offline" role="alert">
          <strong>Backend unreachable.</strong> Start it with <code>make backend</code> (127.0.0.1:8000). Showing the last
          confirmed data{lastSyncAt ? ` from ${new Date(lastSyncAt).toLocaleTimeString()}` : ""}; retrying automatically.
        </div>
      )}
      {connection === "online" && syncError && (
        <div className="offline offline--warn" role="alert">
          Sync problem: {syncError}
        </div>
      )}

      <OutcomeBanner pending={pending} outcome={outcome} onDismiss={dismissOutcome} />

      <main className="main" role="tabpanel" aria-label={active.label}>
        <active.Page />
      </main>

      <footer className="footer">
        <span>{SIMULATION_NOTICE}</span>
        <span>Synthetic data · deterministic mock scenarios · no real aircraft, avionics or ATC</span>
      </footer>
    </div>
  );
}
