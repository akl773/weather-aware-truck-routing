/** The browser's time zone as a short name, like "MDT" (ui D3). */
export function zoneName(at: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-US", { timeZoneName: "short" }).formatToParts(at);
  return parts.find((part) => part.type === "timeZoneName")?.value ?? "";
}

/** "Mon 2:05 PM" in the browser's zone (ui D3). */
export function formatTime(iso: string | Date): string {
  const time = new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
  });
  return time.format(typeof iso === "string" ? new Date(iso) : iso);
}

/** "7 h 23 min", "45 min". */
export function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = Math.round(minutes - hours * 60);
  return hours > 0 ? `${hours} h ${rest} min` : `${rest} min`;
}

/** "1,023.3 mi". The API rounds; this only pads and groups (recommendation D4). */
export function formatMiles(miles: number): string {
  return `${miles.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} mi`;
}

/** A reading as the API rounded it, padded to its precision; "—" when unknown. */
export function formatReading(value: number | null, digits: number, unit: string): string {
  return value === null ? "—" : `${value.toFixed(digits)} ${unit}`;
}
