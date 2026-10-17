import { useEffect, useRef, useState } from "react";
import { OutcomeBanner } from "./components/OutcomeBanner";
import { Sidebar } from "./components/Sidebar";
import { TopTelemetryBar } from "./components/TopTelemetryBar";
import { useAeroGuard } from "./hooks/useAeroGuard";
import { ATCPage } from "./pages/ATCPage";
import { BlackBoxPage } from "./pages/BlackBoxPage";
import { CockpitPage } from "./pages/CockpitPage";
import { FlightDeckPage } from "./pages/FlightDeckPage";
import { GuardianPage } from "./pages/GuardianPage";
import { SentinelPage } from "./pages/SentinelPage";
import { SimulationPage } from "./pages/SimulationPage";
import { SimulatorPage } from "./pages/SimulatorPage";
import { VisionPage } from "./pages/VisionPage";
import { soundEffects } from "./utils/soundEffects";

export const SIMULATION_NOTICE = "SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE";

const TABS = [
  { id: "deck", label: "Flight Deck", Page: FlightDeckPage },
  { id: "guardian", label: "Guardian", Page: GuardianPage },
  { id: "sentinel", label: "Sentinel", Page: SentinelPage },
  { id: "vision", label: "Vision", Page: VisionPage },
  { id: "simulator", label: "Simulator", Page: SimulatorPage },
  { id: "blackbox", label: "Black Box", Page: BlackBoxPage },
  { id: "scenarios", label: "Scenarios", Page: SimulationPage },
  { id: "simulation", label: "Emergency Simulation", Page: SimulationPage },
  { id: "cockpit", label: "Cockpit Monitoring", Page: CockpitPage },
  { id: "atc", label: "Fictional ATC", Page: ATCPage },
] as const;

type TabId = (typeof TABS)[number]["id"];

function tabFromHash(): TabId {
  const hash = window.location.hash.replace("#", "").toLowerCase();
  if (hash === "flight-deck" || hash === "deck") return "deck";
  const found = TABS.find((t) => t.id === hash);
  return found ? found.id : "simulation";
}

export function App() {
  const [tab, setTab] = useState<TabId>(tabFromHash);
  const { snapshot, connection, syncError, lastSyncAt, pending, outcome, dismissOutcome } = useAeroGuard();

  const prevGuardianStateRef = useRef(snapshot?.guardian_state);
  const prevSentinelStateRef = useRef(snapshot?.sentinel_state);
  const prevRunIdRef = useRef(snapshot?.scenario_run_id);
  const prevActionRef = useRef(snapshot?.last_simulator_action?.action_id);
  const prevOutcomeRef = useRef(outcome?.at);

  useEffect(() => {
    const onHash = () => setTab(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // Unlock AudioContext on first user interaction
  useEffect(() => {
    const handleUserInteraction = () => {
      soundEffects.ensureAudioContext();
    };
    window.addEventListener("click", handleUserInteraction, { once: true });
    window.addEventListener("keydown", handleUserInteraction, { once: true });
    return () => {
      window.removeEventListener("click", handleUserInteraction);
      window.removeEventListener("keydown", handleUserInteraction);
    };
  }, []);

  // Scenario & Emergency avionics sound triggers
  useEffect(() => {
    if (!snapshot) return;

    // Scenario started: play scenario-specific sound
    if (snapshot.scenario_run_id && snapshot.scenario_run_id !== prevRunIdRef.current) {
      prevRunIdRef.current = snapshot.scenario_run_id;
      if (snapshot.scenario_id) {
        soundEffects.playScenarioAlert(snapshot.scenario_id);
      }
    }

    // Guardian emergency escalation
    if (snapshot.guardian_state !== prevGuardianStateRef.current) {
      if (snapshot.guardian_state === "ESCALATED") {
        soundEffects.playMasterWarning(2400);
      } else if (snapshot.guardian_state === "AWAITING_ACK" || snapshot.guardian_state === "SUSPECTED") {
        soundEffects.playMasterCaution();
      }
      prevGuardianStateRef.current = snapshot.guardian_state;
    }

    // Sentinel state transition
    if (snapshot.sentinel_state !== prevSentinelStateRef.current) {
      if (snapshot.sentinel_state === "AWAITING_ATC") {
        soundEffects.playATCRadioChime();
      }
      prevSentinelStateRef.current = snapshot.sentinel_state;
    }

    // Simulator action execution
    if (snapshot.last_simulator_action && snapshot.last_simulator_action.action_id !== prevActionRef.current) {
      prevActionRef.current = snapshot.last_simulator_action.action_id;
      soundEffects.playActionTone();
    }
  }, [snapshot]);

  // Audio feedback on accepted pilot acknowledgment & ATC approvals
  useEffect(() => {
    if (!outcome || outcome.at === prevOutcomeRef.current) return;
    prevOutcomeRef.current = outcome.at;

    if (outcome.status === "accepted") {
      const lower = outcome.label.toLowerCase();
      if (lower.includes("acknowledge")) {
        soundEffects.playAckChime();
      } else if (lower.includes("atc") || lower.includes("approve")) {
        soundEffects.playActionTone();
      }
    }
  }, [outcome]);

  const active = TABS.find((t) => t.id === tab) ?? TABS[0];

  return (
    <div className="cyber-dashboard-root">
      {/* Simulation Mandatory Notice Banner */}
      <div className="sim-banner" role="note">
        {SIMULATION_NOTICE}
      </div>

      <div className="cyber-layout-wrapper">
        {/* Left Aerospace Sidebar */}
        <Sidebar currentTab={tab} onSelectTab={(newTab) => setTab(newTab as TabId)} />

        {/* Main Content Area */}
        <div className="cyber-main-content">
          {/* Top Flight Telemetry Strip */}
          <TopTelemetryBar />

          {/* Quick Nav Pill Tabs for direct accessibility */}
          <nav className="tabs tabs--quick" role="tablist" aria-label="Screens">
            {TABS.filter((t) => ["deck", "guardian", "sentinel", "vision", "blackbox", "simulation", "cockpit", "atc"].includes(t.id)).map((t) => (
              <a
                key={t.id}
                href={`#${t.id}`}
                role="tab"
                aria-selected={tab === t.id}
                className={`tabs__tab ${tab === t.id ? "is-active" : ""}`}
                onClick={(e) => {
                  e.preventDefault();
                  window.location.hash = t.id;
                  setTab(t.id);
                }}
              >
                {t.label}
              </a>
            ))}
          </nav>

          {/* Connection Alerts */}
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

          {/* Command Outcome Banner */}
          <OutcomeBanner pending={pending} outcome={outcome} onDismiss={dismissOutcome} />

          {/* Active Screen Tabpanel */}
          <main className="main-viewport" role="tabpanel" aria-label={active.label}>
            <active.Page />
          </main>

          {/* Bottom Compliance Footer */}
          <footer className="cyber-footer">
            <span>{SIMULATION_NOTICE}</span>
            <span>Synthetic flight demonstration · IBM Z Datathon · Non-operational simulation</span>
          </footer>
        </div>
      </div>
    </div>
  );
}
