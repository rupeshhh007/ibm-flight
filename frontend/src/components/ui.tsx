// Small presentational building blocks shared by every screen.
import type { ReactNode } from "react";
import type { Tone } from "./tones";

export function Panel({
  title,
  subtitle,
  actions,
  children,
  className = "",
  tone,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  tone?: Tone;
}) {
  return (
    <section className={`panel ${tone ? `panel--${tone}` : ""} ${className}`} aria-label={title}>
      <header className="panel__head">
        <div>
          <h2 className="panel__title">{title}</h2>
          {subtitle && <p className="panel__subtitle">{subtitle}</p>}
        </div>
        {actions && <div className="panel__actions">{actions}</div>}
      </header>
      <div className="panel__body">{children}</div>
    </section>
  );
}

export function Pill({ tone, children, pulse = false }: { tone: Tone; children: ReactNode; pulse?: boolean }) {
  return (
    <span className={`pill pill--${tone} ${pulse ? "pill--pulse" : ""}`}>
      <span className="pill__dot" aria-hidden="true" />
      {children}
    </span>
  );
}

export function Field({ label, children, mono = false }: { label: string; children: ReactNode; mono?: boolean }) {
  return (
    <div className="field">
      <dt className="field__label">{label}</dt>
      <dd className={`field__value ${mono ? "mono" : ""}`}>{children}</dd>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}

export function Ladder<T extends string>({
  steps,
  current,
  toneOf,
  format,
}: {
  steps: readonly T[];
  current: T;
  toneOf: Record<T, Tone>;
  format: (value: T) => string;
}) {
  return (
    <ol className="ladder" aria-label="State machine">
      {steps.map((step) => (
        <li
          key={step}
          className={`ladder__step ${step === current ? `ladder__step--active ladder__step--${toneOf[step]}` : ""}`}
          aria-current={step === current ? "step" : undefined}
        >
          {format(step)}
        </li>
      ))}
    </ol>
  );
}
