/** The browser's time zone as a short name, like "MDT" (ui D3). */
export function zoneName(at: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-US", { timeZoneName: "short" }).formatToParts(at);
  return parts.find((part) => part.type === "timeZoneName")?.value ?? "";
}

// Built once: a formatter costs far more to create than to use, and a plan formats hundreds of
// ETAs. It reads the browser's zone when created, which does not change while the page is open.
const TIME = new Intl.DateTimeFormat("en-US", {
  weekday: "short",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

/** "Mon, Oct 19, 2:05 PM" in the browser's zone (ui D3); the date tells a week's days apart. */
export function formatTime(iso: string | Date): string {
  return TIME.format(typeof iso === "string" ? new Date(iso) : iso);
}

/** "7 h 23 min", "45 min". */
export function formatDuration(minutes: number): string {
  const total = Math.round(minutes);
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  if (hours === 0) return `${rest} min`;
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`;
}

/** "1,023.3 mi". The API rounds; this only pads and groups (recommendation D4). */
export function formatMiles(miles: number): string {
  return `${miles.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} mi`;
}

/** A reading as the API rounded it, padded to its precision; "—" when unknown. */
export function formatReading(value: number | null, digits: number, unit: string): string {
  return value === null ? "—" : `${value.toFixed(digits)} ${unit}`;
}
