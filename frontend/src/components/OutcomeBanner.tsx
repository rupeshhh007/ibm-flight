import type { CommandOutcome } from "../hooks/useAeroGuard";
import { Icon, type IconName } from "./icons";

const TITLES: Record<CommandOutcome["status"], string> = {
  accepted: "Confirmed by backend",
  duplicate: "Duplicate command — backend returned the original result, nothing re-executed",
  rejected: "Rejected by backend",
  network: "Backend unreachable — command outcome unknown",
  uncertain: "Transport error — command outcome uncertain; backend may have executed the action",
};

const ICONS: Record<CommandOutcome["status"], IconName> = {
  accepted: "check",
  duplicate: "info",
  rejected: "alert",
  network: "unlink",
  uncertain: "alert",
};

/** Flash bar with the backend's verdict on the most recent command. The slot stays mounted so it is always announced. */
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
    <div className="flash-slot" aria-live="polite">
      {pending ? (
        <div className="flash flash--pending" role="status">
          <span className="spinner" aria-hidden="true" />
          <strong>{pending}</strong>
          <span className="flash__msg">— waiting for backend confirmation…</span>
        </div>
      ) : outcome ? (
        <div className={`flash flash--${outcome.status}`} role={outcome.status === "accepted" ? "status" : "alert"}>
          <Icon name={ICONS[outcome.status]} size={16} className="flash__icon" />
          <div className="flash__text">
            <strong>
              {outcome.label}: {TITLES[outcome.status]}
            </strong>
            <span className="flash__msg">
              {outcome.code && <code className="flash__code">{outcome.code}</code>} {outcome.message}
            </span>
            {outcome.details && outcome.details.length > 0 && (
              <ul className="flash__details">
                {outcome.details.map((detail) => (
                  <li key={detail}>{detail}</li>
                ))}
              </ul>
            )}
          </div>
          <div className="flash__actions">
            {outcome.retry && (
              <button type="button" className="btn btn--secondary btn--sm" onClick={outcome.retry}>
                Retry same command
              </button>
            )}
            <button type="button" className="icon-btn" onClick={onDismiss} aria-label="Dismiss message">
              <Icon name="x" size={14} />
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
