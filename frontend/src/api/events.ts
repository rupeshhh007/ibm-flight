// Event-history helpers. The backend assigns every committed event a global,
// strictly increasing `seq`. The browser keeps one ordered list and drops any
// event whose seq it has already seen, so overlapping polls (or a future SSE
// replay) can never duplicate or reorder the audit timeline.
import type { StoredEvent } from "./types";

/** Upper bound on events held in memory; the full history stays queryable via REST. */
export const MAX_EVENTS = 2000;

export function mergeEvents(current: readonly StoredEvent[], incoming: readonly StoredEvent[]): StoredEvent[] {
  if (incoming.length === 0) return current as StoredEvent[];
  const seen = new Set(current.map((event) => event.seq));
  const fresh = incoming.filter((event) => {
    if (seen.has(event.seq)) return false;
    seen.add(event.seq);
    return true;
  });
  if (fresh.length === 0) return current as StoredEvent[];
  const merged = [...current, ...fresh].sort((a, b) => a.seq - b.seq);
  return merged.length > MAX_EVENTS ? merged.slice(merged.length - MAX_EVENTS) : merged;
}

export function latestSeq(events: readonly StoredEvent[]): number {
  return events.length === 0 ? 0 : events[events.length - 1].seq;
}

/** Human-readable label for an EventType value. */
export function eventLabel(type: StoredEvent["event_type"]): string {
  return type
    .toLowerCase()
    .split("_")
    .map((word) => (word === "atc" ? "ATC" : word[0].toUpperCase() + word.slice(1)))
    .join(" ");
}
