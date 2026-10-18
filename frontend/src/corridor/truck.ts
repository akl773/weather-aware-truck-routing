import type { components } from "../api/schema";

type Route = components["schemas"]["Route"];

/**
 * The route mile the truck has reached at `at` (ms since the epoch), interpolated between the
 * checkpoints' ETAs; 0 before departure and the route's end after arrival (corridor-heatmap D7).
 */
export function truckMile(route: Route, at: number): number {
  const stops = route.checkpoints.map((c) => [Date.parse(c.eta), c.mile] as const);
  const first = stops[0];
  const last = stops[stops.length - 1];
  if (!first || !last) return 0;
  if (at <= first[0]) return first[1];
  if (at >= last[0]) return route.summary.distance_mi;
  let i = 1;
  while (i < stops.length - 1 && (stops[i] as (typeof stops)[number])[0] < at) i++;
  const [t0, m0] = stops[i - 1] as (typeof stops)[number];
  const [t1, m1] = stops[i] as (typeof stops)[number];
  return t1 > t0 ? m0 + ((m1 - m0) * (at - t0)) / (t1 - t0) : m1;
}
