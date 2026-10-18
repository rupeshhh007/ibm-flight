// Minimal inline stroke icons (24px grid). Inline SVG keeps the bundle free of an
// icon-library dependency and lets icons inherit `currentColor` from their context.
import type { SVGProps } from "react";

const PATHS = {
  cockpit: "M3 17h18M5 17l2-8h10l2 8M9 9V6h6v3M12 13v4",
  tower: "M12 3v4M8 21l2-12h4l2 12M7 9h10M9 15h6M5 5a8 8 0 0 1 14 0",
  simulation: "M4 5h16v11H4zM8 20h8M12 16v4M10 8.5l4 2.5-4 2.5z",
  shield: "M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z",
  radar: "M12 12l6-6M21 12a9 9 0 1 1-9-9M16.5 12a4.5 4.5 0 1 1-4.5-4.5",
  camera: "M4 7h3l2-2h6l2 2h3v12H4zM12 16a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z",
  plane: "M10.5 21l1.5-1.5 1.5 1.5M12 19.5V14M3 13l9-3 9 3M12 10V4a1.5 1.5 0 0 0-3 0",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
  check: "M5 12.5l4.5 4.5L19 7.5",
  x: "M6 6l12 12M18 6L6 18",
  alert: "M12 4l9 16H3zM12 10v4M12 17v.5",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v6M12 7.5v.5",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  unlink: "M15 9l3-3a3 3 0 0 0-4.2-4.2L11 4.6M9 15l-3 3a3 3 0 0 0 4.2 4.2l2.8-2.8M4 4l16 16",
  play: "M7 5l12 7-12 7z",
  forward: "M5 6l7 6-7 6zM13 6l7 6-7 6z",
  reset: "M4 12a8 8 0 1 0 2.4-5.7M4 4v4h4",
  list: "M8 6h12M8 12h12M8 18h12M4 6h.5M4 12h.5M4 18h.5",
  chevron: "M9 6l6 6-6 6",
  eye: "M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  eyeOff: "M3 3l18 18M10.6 6.1A10 10 0 0 1 12 6c6.4 0 10 6 10 6a17 17 0 0 1-3.2 3.8M6.6 6.6C3.9 8.3 2 12 2 12s3.6 7 10 7a9.6 9.6 0 0 0 4.4-1",
  scenario: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
  deck: "M3 12a9 9 0 0 1 18 0M12 12l4-4M5 16h14M8 20h8",
  vision: "M3 7V4h3M18 4h3v3M21 17v3h-3M6 20H3v-3M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z",
  blackbox: "M4 6h16v12H4zM4 10h16M8 14h3M15 14h1",
  pause: "M8 5v14M16 5v14",
  skipBack: "M18 6l-8 6 8 6zM6 6v12",
  skipFwd: "M6 6l8 6-8 6zM18 6v12",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4",
  signal: "M5 20v-3M10 20v-7M15 20v-11M20 20V4",
  route: "M5 19c3-6 5-2 8-8s5-6 6-6M5 19h.5M19 5h.5",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 16, ...rest }: { name: IconName; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
