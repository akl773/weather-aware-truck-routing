/** The browser's time zone as a short name, like "MDT" (ui D3). */
export function zoneName(at: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-US", { timeZoneName: "short" }).formatToParts(at);
  return parts.find((part) => part.type === "timeZoneName")?.value ?? "";
}
