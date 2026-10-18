import { describe, expect, it } from "vitest";

import type { components } from "../api/schema";
import { labelPoints } from "./labels";

type Route = components["schemas"]["Route"];

function route(id: Route["id"], path: [number, number][]): Route {
  let mile = 0;
  let previous = path[0] as [number, number];
  const withMiles = path.map(([lon, lat]) => {
    mile += 69 * Math.hypot(lon - previous[0], lat - previous[1]);
    previous = [lon, lat];
    return [lon, lat, mile];
  });
  return {
    id,
    fallback: false,
    path: withMiles,
    summary: {
      distance_mi: mile,
      duration_min: 60,
      miles_by_level: { low: mile, moderate: 0, high: 0, severe: 0, no_travel: 0, unknown: 0 },
      mean_level: 0,
    },
    checkpoints: [],
  };
}

// Both run due east along the equator for 10 degrees; B bends a degree north over its middle.
const line = (bend: number): [number, number][] =>
  Array.from({ length: 101 }, (_, i) => [i / 10, i >= 30 && i <= 70 ? bend : 0]);

describe("labelPoints (ui D6)", () => {
  it("puts each letter where its route is farthest from the others", () => {
    const points = labelPoints([route("A", line(0)), route("B", line(1))]);
    expect(points.get("B")?.[1]).toBe(1);
  });

  it("keeps letters off a stretch the routes share", () => {
    const points = labelPoints([route("A", line(0)), route("B", line(1))]);
    expect(points.get("A")).not.toEqual(points.get("B"));
  });

  it("uses the midpoint for a lone route", () => {
    expect(labelPoints([route("A", line(0))]).get("A")?.[0]).toBeCloseTo(5, 5);
  });
});
