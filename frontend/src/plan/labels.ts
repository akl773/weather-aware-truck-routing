import type { components } from "../api/schema";
import { type LngLat, pointAtMile } from "./segments";

type Route = components["schemas"]["Route"];

// Enough points to find a clear stretch on a coast-to-coast route without measuring every pair.
const CANDIDATES = 120;
const NEIGHBOURS = 400;

function sample(path: number[][], count: number, from = 0, to = 1): number[][] {
  const first = Math.floor(from * (path.length - 1));
  const last = Math.ceil(to * (path.length - 1));
  const step = Math.max(1, Math.floor((last - first) / count));
  const points: number[][] = [];
  for (let i = first; i <= last; i += step) points.push(path[i] as number[]);
  return points;
}

/** Squared distance in degrees, with longitude shrunk by latitude so it is roughly ground distance. */
function apart(a: number[], b: number[]): number {
  const shrink = Math.cos((((a[1] as number) + (b[1] as number)) / 2) * (Math.PI / 180));
  const dx = ((a[0] as number) - (b[0] as number)) * shrink;
  const dy = (a[1] as number) - (b[1] as number);
  return dx * dx + dy * dy;
}

/**
 * Where to put each route's letter: the point in the middle 60% of the route that lies farthest
 * from every other route, so letters never sit on a shared stretch where one would hide another
 * (ui D6).
 */
export function labelPoints(routes: Route[]): Map<Route["id"], LngLat> {
  const neighbours = new Map(routes.map((route) => [route.id, sample(route.path, NEIGHBOURS)]));
  const points = new Map<Route["id"], LngLat>();
  for (const route of routes) {
    const others = routes.filter((r) => r.id !== route.id).flatMap((r) => neighbours.get(r.id) ?? []);
    if (route.path.length < 2 || others.length === 0) {
      points.set(route.id, pointAtMile(route, route.summary.distance_mi / 2));
      continue;
    }
    let best: number[] = route.path[0] as number[];
    let bestApart = -1;
    for (const candidate of sample(route.path, CANDIDATES, 0.2, 0.8)) {
      let nearest = Infinity;
      for (const other of others) nearest = Math.min(nearest, apart(candidate, other));
      if (nearest > bestApart) [best, bestApart] = [candidate, nearest];
    }
    points.set(route.id, [best[0] as number, best[1] as number]);
  }
  return points;
}
