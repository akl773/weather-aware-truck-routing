import type { components } from "../api/schema";

type Route = components["schemas"]["Route"];
export type LngLat = [number, number];

export interface Segment {
  routeId: Route["id"];
  checkpointIndex: number;
  level: number | null;
  path: LngLat[];
}

/** The point at `mile` along a path of `[lon, lat, mile]` triples, starting the search at `from`. */
function pointAt(path: number[][], mile: number, from: number): { point: LngLat; index: number } {
  let i = Math.max(1, from);
  while (i < path.length - 1 && (path[i]?.[2] ?? 0) < mile) i++;
  const a = path[i - 1] as number[];
  const b = path[i] as number[];
  const span = (b[2] as number) - (a[2] as number);
  const t = span > 0 ? Math.min(1, Math.max(0, (mile - (a[2] as number)) / span)) : 0;
  return {
    point: [
      (a[0] as number) + ((b[0] as number) - (a[0] as number)) * t,
      (a[1] as number) + ((b[1] as number) - (a[1] as number)) * t,
    ],
    index: i,
  };
}

/** Each checkpoint's owned stretch of the route, to draw in its level's colour (ui D6). */
export function routeSegments(route: Route): Segment[] {
  const { path } = route;
  if (path.length < 2) return [];
  const segments: Segment[] = [];
  let cursor = 1;
  route.checkpoints.forEach((checkpoint, checkpointIndex) => {
    const start = pointAt(path, checkpoint.owned_from_mi, cursor);
    const end = pointAt(path, checkpoint.owned_to_mi, start.index);
    const inner = path
      .slice(start.index, end.index)
      .filter((p) => (p[2] as number) > checkpoint.owned_from_mi && (p[2] as number) < checkpoint.owned_to_mi)
      .map((p) => [p[0], p[1]] as LngLat);
    segments.push({
      routeId: route.id,
      checkpointIndex,
      level: checkpoint.level,
      path: [start.point, ...inner, end.point],
    });
    cursor = end.index;
  });
  return segments;
}

/** Where along the path a mile falls, for markers and labels. */
export function pointAtMile(route: Route, mile: number): LngLat {
  return pointAt(route.path, mile, 1).point;
}
