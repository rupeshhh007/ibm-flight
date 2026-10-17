import type { ReactNode } from "react";
import { useAeroGuard } from "../hooks/useAeroGuard";

export interface NavItem {
  id: string;
  label: string;
  icon: ReactNode;
  badge?: number | string | boolean;
}

interface SidebarProps {
  currentTab: string;
  onSelectTab: (id: string) => void;
}

export function Sidebar({ currentTab, onSelectTab }: SidebarProps) {
  const { snapshot } = useAeroGuard();

  const isIncident = Boolean(snapshot?.active_incident);
  const isAwaitingATC = snapshot?.sentinel_state === "AWAITING_ATC";

  const navItems: NavItem[] = [
    {
      id: "deck",
      label: "Flight Deck",
      icon: (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
        </svg>
      ),
    },
    {
      id: "guardian",
      label: "Guardian",
      icon: (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        </svg>
      ),
      badge: isIncident,
    },
    {
      id: "sentinel",
      label: "Sentinel",
      icon: (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="2" />
          <path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14" />
        </svg>
      ),
      badge: isAwaitingATC ? "REQ" : undefined,
    },
    {
      id: "vision",
      label: "Vision",
      icon: (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M23 7l-7 5 7 5V7z" />
          <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
        </svg>
      ),
    },
    {
      id: "simulator",
      label: "Simulator",
      icon: (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
          <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
          <line x1="12" y1="22.08" x2="12" y2="12" />
        </svg>
      ),
    },
    {
      id: "blackbox",
      label: "Black Box",
      icon: (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <polygon points="10 8 16 12 10 16 10 8" />
        </svg>
      ),
    },
    {
      id: "simulation",
      label: "Scenarios",
      icon: (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="8" y1="6" x2="21" y2="6" />
          <line x1="8" y1="12" x2="21" y2="12" />
          <line x1="8" y1="18" x2="21" y2="18" />
          <line x1="3" y1="6" x2="3.01" y2="6" />
          <line x1="3" y1="12" x2="3.01" y2="12" />
          <line x1="3" y1="18" x2="3.01" y2="18" />
        </svg>
      ),
    },
    {
      id: "cockpit",
      label: "Cockpit Desk",
      icon: (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
          <circle cx="12" cy="7" r="4" />
        </svg>
      ),
    },
    {
      id: "atc",
      label: "ATC Console",
      icon: (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="22" />
        </svg>
      ),
      badge: isAwaitingATC,
    },
  ];

  return (
    <aside className="cyber-sidebar">
      <div className="cyber-sidebar__brand">
        <div className="cyber-sidebar__logo">
          <svg viewBox="0 0 32 32" className="cyber-logo-icon" aria-hidden="true">
            <path
              d="M16 3 L27 8 V16 C27 22.5 22.4 27.4 16 29 C9.6 27.4 5 22.5 5 16 V8 Z"
              fill="rgba(56, 189, 248, 0.15)"
              stroke="#38bdf8"
              strokeWidth="2"
            />
            <path
              d="M16 10 L17.6 15 L23 16.5 L17.6 18 L16 23 L14.4 18 L9 16.5 L14.4 15 Z"
              fill="#38bdf8"
            />
          </svg>
        </div>
        <div>
          <h1 className="cyber-sidebar__title">AEROGUARD</h1>
          <span className="cyber-sidebar__subtitle">AI FLIGHT SAFETY SYSTEM</span>
        </div>
      </div>

      <nav className="cyber-sidebar__nav" role="tablist">
        {navItems.map((item) => {
          const isActive = currentTab === item.id;
          return (
            <a
              key={item.id}
              href={`#${item.id}`}
              role="tab"
              aria-selected={isActive}
              className={`cyber-nav-item ${isActive ? "is-active" : ""}`}
              onClick={(e) => {
                e.preventDefault();
                window.location.hash = item.id;
                onSelectTab(item.id);
              }}
            >
              <span className="cyber-nav-item__icon">{item.icon}</span>
              <span className="cyber-nav-item__label">{item.label}</span>
              {item.badge && (
                <span className="cyber-nav-item__badge" aria-label="Action required">
                  {typeof item.badge === "string" ? item.badge : "●"}
                </span>
              )}
            </a>
          );
        })}
      </nav>

      <div className="cyber-sidebar__footer">
        <div className="cyber-plane-card">
          <div className="cyber-plane-meta">
            <span className="cyber-plane-callsign">SIM-001</span>
            <span className="cyber-plane-type">Boeing 737 (Simulated)</span>
          </div>
          <div className={`cyber-plane-status ${isIncident ? "is-alert" : "is-nominal"}`}>
            <span className="cyber-status-pulse" />
            <span>{isIncident ? "INCIDENT ACTIVE" : "SYSTEMS NOMINAL"}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
