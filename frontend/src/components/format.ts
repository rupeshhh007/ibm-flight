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

export function formatNumber(value: number, digits = 0): string {
  return value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function humanize(value: string): string {
  return value
    .toLowerCase()
    .split("_")
    .map((word) => (word === "atc" ? "ATC" : word === "sim" ? "Sim" : word[0].toUpperCase() + word.slice(1)))
    .join(" ");
}
