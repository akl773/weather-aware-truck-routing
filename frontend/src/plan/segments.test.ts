import { describe, expect, it } from "vitest";

import type { components } from "../api/schema";
import { pointAtMile, routeSegments } from "./segments";

type Route = components["schemas"]["Route"];

function checkpoint(mile: number, from: number, to: number, level: number | null) {
  return {
    mile,
    lat: 0,
    lon: mile / 10,
    eta: "2026-10-19T18:00:00Z",
    owned_from_mi: from,
    owned_to_mi: to,
    readings: { wind_mph: 10, gust_mph: 12, rain_in_hr: 0, snow_in_hr: 0 },
    level,
    drivers: [],
    gusty: false,
  };
}

// Due east along the equator, a mile per tenth of a degree for easy reading.
const ROUTE: Route = {
  id: "A",
  fallback: false,
  path: [
    [0, 0, 0],
    [1, 0, 10],
    [2, 0, 20],
    [3, 0, 30],
  ],
  summary: {
    distance_mi: 30,
    duration_min: 30,
    miles_by_level: { low: 5, moderate: 10, high: 0, severe: 0, no_travel: 0, unknown: 15 },
    mean_level: 0.67,
  },
  checkpoints: [checkpoint(0, 0, 5, 0), checkpoint(10, 5, 15, 1), checkpoint(30, 15, 30, null)],
};

describe("routeSegments (ui D6)", () => {
  it("cuts the path at each owned stretch's ends", () => {
    expect(routeSegments(ROUTE).map((s) => s.path)).toEqual([
      [
        [0, 0],
        [0.5, 0],
      ],
      [
        [0.5, 0],
        [1, 0],
        [1.5, 0],
      ],
      [
        [1.5, 0],
        [2, 0],
        [3, 0],
      ],
    ]);
  });

  it("colours each stretch by its checkpoint's level, unknown included", () => {
    expect(routeSegments(ROUTE).map((s) => s.level)).toEqual([0, 1, null]);
  });

  it("leaves no gap between stretches", () => {
    const segments = routeSegments(ROUTE);
    for (let i = 1; i < segments.length; i++) {
      expect(segments[i]?.path[0]).toEqual(segments[i - 1]?.path.at(-1));
    }
  });

  it("puts a stretch boundary on a path point without repeating it", () => {
    const route = { ...ROUTE, checkpoints: [checkpoint(0, 0, 10, 0), checkpoint(30, 10, 30, 2)] };
    expect(routeSegments(route).map((s) => s.path.length)).toEqual([2, 3]);
  });

  it("finds a point by mile", () => {
    expect(pointAtMile(ROUTE, 25)).toEqual([2.5, 0]);
    expect(pointAtMile(ROUTE, 99)).toEqual([3, 0]);
  });
});
