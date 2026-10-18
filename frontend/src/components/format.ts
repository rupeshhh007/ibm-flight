export function shortId(id: string | null | undefined): string {
  return id ? id.slice(0, 8) : "—";
}

/** Virtual time is shown as UTC clock time (the simulation clock, not the viewer's clock). */
export function formatVirtualTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return `${date.toISOString().slice(11, 23)}Z`;
}

/** Compact HH:MM:SS (UTC) for dense lists and the context strip. */
export function formatClock(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toISOString().slice(11, 19);
}

export function formatNumber(value: number, digits = 0): string {
  return value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** Flight level is altitude in hundreds of feet, e.g. 35,000 ft → FL350. */
export function formatFlightLevel(altitudeFt: number): string {
  return `FL${String(Math.max(0, Math.round(altitudeFt / 100))).padStart(3, "0")}`;
}

export function formatHeading(deg: number): string {
  return `${String(Math.round(deg) % 360).padStart(3, "0")}°`;
}

export function humanize(value: string): string {
  return value
    .toLowerCase()
    .split("_")
    .map((word) => (word === "atc" ? "ATC" : word === "sim" ? "Sim" : word === "op" ? "Op" : word[0].toUpperCase() + word.slice(1)))
    .join(" ");
}

export function pilotLabel(pilotId: string): string {
  return pilotId === "PILOT_1" ? "Pilot 1" : pilotId === "PILOT_2" ? "Pilot 2" : humanize(pilotId);
}
