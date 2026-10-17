import type { CommandOutcome } from "../hooks/useAeroGuard";

const TITLES: Record<CommandOutcome["status"], string> = {
  accepted: "Confirmed by backend",
  duplicate: "Duplicate command — backend returned the original result, nothing re-executed",
  rejected: "Rejected by backend",
  network: "Backend unreachable — command outcome unknown",
};

/** Shows the backend's verdict on the most recent command; announced to screen readers. */
export function OutcomeBanner({
  pending,
  outcome,
  onDismiss,
}: {
  pending: string | null;
  outcome: CommandOutcome | null;
  onDismiss: () => void;
}) {
  return (
    <div className="outcome-slot" aria-live="polite">
      {pending ? (
        <div className="outcome outcome--pending" role="status">
          <span className="spinner" aria-hidden="true" />
          <strong>{pending}</strong>
          <span>— waiting for backend confirmation…</span>
        </div>
      ) : outcome ? (
        <div className={`outcome outcome--${outcome.status}`} role={outcome.status === "accepted" ? "status" : "alert"}>
          <div className="outcome__text">
            <strong>
              {outcome.label}: {TITLES[outcome.status]}
            </strong>
            <span>
              {outcome.code && <code className="outcome__code">{outcome.code}</code>} {outcome.message}
            </span>
            {outcome.details && outcome.details.length > 0 && (
              <ul className="outcome__details">
                {outcome.details.map((detail) => (
                  <li key={detail}>{detail}</li>
                ))}
              </ul>
            )}
          </div>
          <div className="outcome__actions">
            {outcome.retry && (
              <button type="button" className="btn btn--small" onClick={outcome.retry}>
                Retry same command
              </button>
            )}
            <button type="button" className="btn btn--ghost btn--small" onClick={onDismiss} aria-label="Dismiss message">
              ✕
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
