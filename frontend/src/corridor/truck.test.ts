import { describe, expect, it } from "vitest";

import type { components } from "../api/schema";
import { truckMile } from "./truck";

type Route = components["schemas"]["Route"];

const DEPART = Date.parse("2026-10-19T12:00:00Z");
const HOUR = 3_600_000;

function checkpoint(mile: number, hours: number) {
  return {
    mile,
    lat: 0,
    lon: 0,
    eta: new Date(DEPART + hours * HOUR).toISOString(),
    owned_from_mi: mile,
    owned_to_mi: mile,
    readings: { wind_mph: 0, gust_mph: 0, rain_in_hr: 0, snow_in_hr: 0 },
    level: 0,
    drivers: [],
    gusty: false,
  };
}

// 50 mph for an hour, then 25 mph for two: the truck's pace changes between checkpoints.
const ROUTE: Route = {
  id: "A",
  fallback: false,
  path: [
    [0, 0, 0],
    [1, 0, 100],
  ],
  summary: {
    distance_mi: 100,
    duration_min: 180,
    miles_by_level: { low: 100, moderate: 0, high: 0, severe: 0, no_travel: 0, unknown: 0 },
    mean_level: 0,
  },
  checkpoints: [checkpoint(0, 0), checkpoint(50, 1), checkpoint(100, 3)],
};

describe("truckMile (corridor-heatmap D7)", () => {
  it("waits at the start before departure", () => {
    expect(truckMile(ROUTE, DEPART - HOUR)).toBe(0);
  });

  it("follows each leg's own pace", () => {
    expect(truckMile(ROUTE, DEPART + 0.5 * HOUR)).toBe(25);
    expect(truckMile(ROUTE, DEPART + 1 * HOUR)).toBe(50);
    expect(truckMile(ROUTE, DEPART + 2 * HOUR)).toBe(75);
  });

  it("stays at the destination after arrival", () => {
    expect(truckMile(ROUTE, DEPART + 3 * HOUR)).toBe(100);
    expect(truckMile(ROUTE, DEPART + 40 * HOUR)).toBe(100);
  });
});
