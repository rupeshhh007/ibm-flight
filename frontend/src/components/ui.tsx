// Design-system primitives shared by every screen. Pages compose these instead of
// styling things ad hoc, so the three consoles stay visually consistent.
import type { ReactNode } from "react";
import { Icon, type IconName } from "./icons";
import type { Tone } from "./tones";

/** A titled container: small uppercase header, optional description/actions, then content. */
export function Panel({
  title,
  description,
  actions,
  count,
  icon,
  children,
  className = "",
  tone,
  flush = false,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  count?: ReactNode;
  icon?: IconName;
  children: ReactNode;
  className?: string;
  tone?: Tone;
  /** Removes body padding, for tables and full-bleed displays. */
  flush?: boolean;
}) {
  return (
    <section className={`panel ${tone ? `panel--${tone}` : ""} ${className}`} aria-label={title}>
      <header className="panel__head">
        <div className="panel__heading">
          <h2 className="panel__title">
            {icon && <Icon name={icon} size={15} className="panel__icon" />}
            {title}
            {count !== undefined && <span className="panel__count">({count})</span>}
          </h2>
          {description && <p className="panel__desc">{description}</p>}
        </div>
        {actions && <div className="panel__actions">{actions}</div>}
      </header>
      <div className={`panel__body ${flush ? "panel__body--flush" : ""}`}>{children}</div>
    </section>
  );
}

/** Status label. Colour is never the only signal: the text always states the status. */
export function Badge({
  tone,
  children,
  icon,
  live = false,
  solid = false,
}: {
  tone: Tone;
  children: ReactNode;
  icon?: IconName;
  live?: boolean;
  solid?: boolean;
}) {
  return (
    <span className={`badge badge--${tone} ${solid ? "badge--solid" : ""} ${live ? "badge--live" : ""}`}>
      {icon ? <Icon name={icon} size={12} /> : <span className="badge__dot" aria-hidden="true" />}
      {children}
    </span>
  );
}

/** Label/value pair inside a <dl className="kv">. */
export function KV({ label, children, mono = false, wide = false }: { label: string; children: ReactNode; mono?: boolean; wide?: boolean }) {
  return (
    <div className={`kv__item ${wide ? "kv__item--wide" : ""}`}>
      <dt className="kv__label">{label}</dt>
      <dd className={`kv__value ${mono ? "mono" : ""}`}>{children}</dd>
    </div>
  );
}

/** A large, scannable instrument value (telemetry, counts). */
export function Stat({ label, value, unit }: { label: string; value: ReactNode; unit?: string }) {
  return (
    <div className="stat">
      <span className="stat__label">{label}</span>
      <span className="stat__value mono">
        {value}
        {unit && <span className="stat__unit">{unit}</span>}
      </span>
    </div>
  );
}

export function Empty({ children, icon = "info" }: { children: ReactNode; icon?: IconName }) {
  return (
    <div className="empty">
      <Icon name={icon} size={16} />
      <p>{children}</p>
    </div>
  );
}

/**
 * Inline contextual message (info / warning / error), like a console flash bar.
 * `live` marks a notice that appears dynamically and must be announced.
 */
export function Notice({ tone = "info", title, children, live = false }: { tone?: Tone; title?: ReactNode; children?: ReactNode; live?: boolean }) {
  const icon: IconName = tone === "alert" ? "alert" : tone === "warn" ? "alert" : tone === "ok" ? "check" : "info";
  const role = live ? (tone === "alert" || tone === "warn" ? "alert" : "status") : "note";
  return (
    <div className={`notice notice--${tone}`} role={role}>
      <Icon name={icon} size={16} className="notice__icon" />
      <div className="notice__text">
        {title && <strong className="notice__title">{title}</strong>}
        {children && <span>{children}</span>}
      </div>
    </div>
  );
}

/**
 * Horizontal state track. `steps` are shown in order; steps up to the current one
 * are filled, which conveys "level reached" on an ordered scale. `alternates` are
 * off-track states (e.g. RECOVERING, ABORTED) shown as separate chips.
 */
export function StateTrack<T extends string>({
  steps,
  alternates = [],
  current,
  toneOf,
  format,
  label,
}: {
  steps: readonly T[];
  alternates?: readonly T[];
  current: T;
  toneOf: Record<T, Tone>;
  format: (value: T) => string;
  label: string;
}) {
  const index = steps.indexOf(current);
  const tone = toneOf[current];
  return (
    <div className="track" role="group" aria-label={`${label}: ${format(current)}`}>
      <ol className="track__steps">
        {steps.map((step, i) => {
          const state = i === index ? "current" : index >= 0 && i < index ? "reached" : "idle";
          return (
            <li key={step} className={`track__step track__step--${state} ${state !== "idle" ? `track__step--${tone}` : ""}`} aria-current={state === "current" ? "step" : undefined}>
              <span className="track__node" aria-hidden="true" />
              <span className="track__label">{format(step)}</span>
            </li>
          );
        })}
      </ol>
      {alternates.length > 0 && (
        <div className="track__alts">
          {alternates.map((alt) => (
            <span key={alt} className={`track__alt ${alt === current ? `track__alt--current track__alt--${toneOf[alt]}` : ""}`} aria-current={alt === current ? "step" : undefined}>
              {format(alt)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/** Accessible on/off switch. */
export function Switch({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className={`switch ${checked ? "is-on" : ""}`}
      disabled={disabled}
      onClick={() => onChange(!checked)}
    >
      <span className="switch__thumb" aria-hidden="true" />
    </button>
  );
}

export function Segmented<T extends string | number>({
  options,
  value,
  onChange,
  label,
  format = String,
}: {
  options: readonly T[];
  value: T;
  onChange: (next: T) => void;
  label: string;
  format?: (value: T) => string;
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={String(option)}
          type="button"
          className={option === value ? "is-active" : ""}
          aria-pressed={option === value}
          onClick={() => onChange(option)}
        >
          {format(option)}
        </button>
      ))}
    </div>
  );
}

/** Page title row used at the top of every console. */
export function PageHeader({ title, description, actions }: { title: string; description: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <h1 className="page-header__title">{title}</h1>
        <p className="page-header__desc">{description}</p>
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </div>
  );
}
