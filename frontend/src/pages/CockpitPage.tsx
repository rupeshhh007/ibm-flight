import { IncidentCard, IncidentList, GuardianPanel } from "../components/StatePanels";
import { PilotPanel } from "../components/PilotPanel";
import { TelemetryPanel } from "../components/TelemetryPanel";
import { Empty, Panel } from "../components/ui";
import { PILOT_IDS } from "../api/types";
import { useAeroGuard } from "../hooks/useAeroGuard";

export function CockpitPage() {
  const { snapshot, incidents, pending, commands } = useAeroGuard();
  if (!snapshot) return <Empty>Loading cockpit state from the backend…</Empty>;

  const incident = snapshot.active_incident ?? null;
  const pilots = PILOT_IDS.map(
    (id) => snapshot.pilots.find((p) => p.pilot_id === id) ?? { pilot_id: id, latest_observation: null },
  );

  return (
    <div className="grid grid--cockpit">
      <div className="area-pilots grid grid--2">
        {pilots.map((pilot) => (
          <PilotPanel key={pilot.pilot_id} pilot={pilot} />
        ))}
      </div>
      <div className="stack">
        <TelemetryPanel telemetry={snapshot.telemetry} />
        <Panel title="Incident history" subtitle="All runs, from GET /api/v1/incidents">
          <IncidentList incidents={incidents} activeId={incident?.incident_id} />
        </Panel>
      </div>
      <div className="stack">
        <GuardianPanel state={snapshot.guardian_state} />
        <Panel title="Active incident & pilot acknowledgement">
          {incident ? (
            <IncidentCard incident={incident}>
              <div className="ack" role="group" aria-label="Pilot acknowledgement">
                <p className="meta">
                  An acknowledgement is sent to the backend for the active incident. Guardian decides what it means.
                </p>
                <div className="btn-row">
                  {PILOT_IDS.map((id) => (
                    <button
                      key={id}
                      type="button"
                      className="btn btn--primary"
                      disabled={pending !== null}
                      onClick={() => commands.acknowledge(id)}
                    >
                      Acknowledge as {id === "PILOT_1" ? "Pilot 1" : "Pilot 2"}
                    </button>
                  ))}
                </div>
              </div>
            </IncidentCard>
          ) : (
            <Empty>
              No active incident. Guardian state is reported above; acknowledgement controls appear when an alert exists.
            </Empty>
          )}
        </Panel>
      </div>
    </div>
  );
}
