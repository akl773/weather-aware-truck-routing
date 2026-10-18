import type { Place, PlanRequest } from "../api/client";
import type { components } from "../api/schema";

export type IntervalMi = components["schemas"]["IntervalMiEnum"];

// The same bounds as the API (plan-api D1); the form checks them first (ui D4).
export const INTERVALS_MI: readonly IntervalMi[] = [10, 25, 50];
export const DEFAULT_INTERVAL_MI: IntervalMi = 25;
export const MAX_LOAD_LB = 80_000;
export const DEPARTURE_PAST_MS = 60 * 60 * 1000;
export const DEPARTURE_AHEAD_MS = 7 * 24 * 60 * 60 * 1000;
export const MIN_TRIP_MI = 1;

export interface TripDraft {
  origin: Place | null;
  destination: Place | null;
  /** `YYYY-MM-DDTHH:mm` in the browser's time zone, as the native input holds it. */
  departure: string;
  /** As typed; thousands separators allowed. */
  loadLb: string;
  intervalMi: IntervalMi;
}

export type TripField = "origin" | "destination" | "departure" | "loadLb";
export type TripErrors = Partial<Record<TripField, string>>;

/** The form's field order, which is also the order the first error takes focus in. */
export const FIELD_ORDER: readonly TripField[] = ["origin", "destination", "departure", "loadLb"];

const pad = (n: number) => String(n).padStart(2, "0");

/** A date as the native `datetime-local` input writes it, in the browser's zone. */
export function toLocalInput(date: Date): string {
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

/** The local input value as an ISO 8601 instant with the browser's UTC offset (ui D3). */
export function toOffsetIso(date: Date): string {
  const offset = -date.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const zone = `${sign}${pad(Math.floor(Math.abs(offset) / 60))}:${pad(Math.abs(offset) % 60)}`;
  return `${toLocalInput(date)}:00${zone}`;
}

/** `YYYY-MM-DDTHH:mm` read in the browser's zone, or `null` if it is not a real date and time. */
export function parseLocalInput(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) return null;
  const [year, month, day, hour, minute] = match.slice(1, 6).map(Number) as [
    number,
    number,
    number,
    number,
    number,
  ];
  const date = new Date(year, month - 1, day, hour, minute);
  // Rejects 31 February and the like, which Date would roll into the next month.
  return date.getMonth() === month - 1 && date.getDate() === day ? date : null;
}

export function nextFullHour(now: Date): Date {
  const next = new Date(now);
  next.setMinutes(0, 0, 0);
  next.setHours(next.getHours() + 1);
  return next;
}

export function defaultDraft(now: Date): TripDraft {
  return {
    origin: null,
    destination: null,
    departure: toLocalInput(nextFullHour(now)),
    loadLb: "",
    intervalMi: DEFAULT_INTERVAL_MI,
  };
}

/** Great-circle miles on the same earth radius the API uses. */
export function haversineMi(a: Place, b: Place): number {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLon = (b.lon - a.lon) * rad;
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * 3958.8 * Math.asin(Math.sqrt(h));
}

export function parseLoad(text: string): number | null {
  const digits = text.replace(/[,\s]/g, "");
  return /^\d+$/.test(digits) ? Number(digits) : null;
}

export type Validation = { errors: TripErrors; request: PlanRequest | null };

/** Every check the API makes (plan-api D1), and the request to send if all pass (ui D4). */
export function validateTrip(draft: TripDraft, now: Date): Validation {
  const errors: TripErrors = {};
  if (!draft.origin) errors.origin = "Pick a starting place from the suggestions.";
  if (!draft.destination) errors.destination = "Pick a destination from the suggestions.";
  if (
    draft.origin &&
    draft.destination &&
    haversineMi(draft.origin, draft.destination) < MIN_TRIP_MI
  ) {
    errors.destination = "Pick a destination at least a mile from the start.";
  }

  const departure = parseLocalInput(draft.departure);
  if (!departure) {
    errors.departure = "Enter a date and time.";
  } else if (departure.getTime() < now.getTime() - DEPARTURE_PAST_MS) {
    errors.departure = "Departure can be at most an hour ago.";
  } else if (departure.getTime() > now.getTime() + DEPARTURE_AHEAD_MS) {
    errors.departure = "Departure can be at most 7 days ahead; the forecast ends there.";
  }

  const load = parseLoad(draft.loadLb);
  if (draft.loadLb.trim() === "") {
    errors.loadLb = "Enter pounds; 0 if empty.";
  } else if (load === null) {
    errors.loadLb = "Enter whole pounds, like 30000.";
  } else if (load > MAX_LOAD_LB) {
    errors.loadLb = `At most ${MAX_LOAD_LB.toLocaleString("en-US")} lb.`;
  }

  if (Object.keys(errors).length > 0 || !draft.origin || !draft.destination || !departure) {
    return { errors, request: null };
  }
  return {
    errors,
    request: {
      origin: draft.origin,
      destination: draft.destination,
      departure: toOffsetIso(departure),
      load_lb: load as number,
      interval_mi: draft.intervalMi,
    },
  };
}
