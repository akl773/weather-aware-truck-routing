import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  type TripDraft,
  defaultDraft,
  haversineMi,
  nextFullHour,
  parseLoad,
  parseLocalInput,
  toLocalInput,
  toOffsetIso,
  validateTrip,
} from "./draft";

const DENVER = { label: "Denver, CO, USA", lat: 39.7392, lon: -104.9903 };
const SALT_LAKE_CITY = { label: "Salt Lake City, UT, USA", lat: 40.7608, lon: -111.891 };
// One mile of latitude in degrees, on the API's haversine earth.
const MILE_DEG = (1 / 3958.8) * (180 / Math.PI);

// Local time is read in the zone the tests run in; pin it so offsets are predictable.
const ORIGINAL_TZ = process.env.TZ;
beforeEach(() => {
  process.env.TZ = "America/Denver";
});
afterEach(() => {
  process.env.TZ = ORIGINAL_TZ;
  vi.useRealTimers();
});

const NOW = () => new Date("2026-10-19T18:00:00Z"); // 12:00 in Denver (MDT, UTC-6)

function draft(changes: Partial<TripDraft> = {}): TripDraft {
  return {
    origin: DENVER,
    destination: SALT_LAKE_CITY,
    departure: "2026-10-19T14:00",
    loadLb: "30,000",
    intervalMi: 25,
    ...changes,
  };
}

describe("departure (ui D3)", () => {
  it("is sent as the local instant with the browser's UTC offset", () => {
    expect(validateTrip(draft(), NOW()).request?.departure).toBe("2026-10-19T14:00:00-06:00");
  });

  it("carries the winter offset after daylight saving ends", () => {
    expect(toOffsetIso(new Date(2026, 11, 1, 9, 30))).toBe("2026-12-01T09:30:00-07:00");
  });

  it("defaults to the next full hour", () => {
    expect(defaultDraft(NOW()).departure).toBe("2026-10-19T13:00");
    expect(toLocalInput(nextFullHour(new Date(2026, 9, 19, 12, 59)))).toBe("2026-10-19T13:00");
  });

  it("rejects dates the calendar does not have", () => {
    expect(parseLocalInput("2026-02-30T12:00")).toBeNull();
    expect(parseLocalInput("2026-10-19")).toBeNull();
    expect(parseLocalInput("2026-02-28T12:00")).not.toBeNull();
  });

  it.each([
    ["2026-10-19T11:00", true], // exactly an hour ago
    ["2026-10-19T10:59", false],
    ["2026-10-26T12:00", true], // exactly seven days ahead
    ["2026-10-26T12:01", false],
  ])("from an hour ago to seven days ahead: %s is valid: %s", (departure, ok) => {
    expect(validateTrip(draft({ departure }), NOW()).errors.departure === undefined).toBe(ok);
  });
});

describe("load (ui D4)", () => {
  it.each([
    ["0", 0],
    ["80000", 80_000],
    ["80,000", 80_000],
    [" 30 000 ", 30_000],
  ])("accepts %j as %d lb", (text, lb) => {
    expect(validateTrip(draft({ loadLb: text }), NOW()).request?.load_lb).toBe(lb);
  });

  it.each(["80001", "-1", "1.5", "30k", ""])("rejects %j", (text) => {
    const { errors, request } = validateTrip(draft({ loadLb: text }), NOW());
    expect(errors.loadLb).toBeDefined();
    expect(request).toBeNull();
  });

  it("reads separators but not other characters", () => {
    expect(parseLoad("12,345")).toBe(12_345);
    expect(parseLoad("12.345")).toBeNull();
  });
});

describe("places (ui D2, D4)", () => {
  it("needs both places picked", () => {
    const { errors, request } = validateTrip(draft({ origin: null, destination: null }), NOW());
    expect(Object.keys(errors)).toEqual(["origin", "destination"]);
    expect(request).toBeNull();
  });

  it("accepts places just over a mile apart and rejects them just under", () => {
    const over = { ...DENVER, lat: DENVER.lat + 1.01 * MILE_DEG };
    const under = { ...DENVER, lat: DENVER.lat + 0.99 * MILE_DEG };
    expect(validateTrip(draft({ destination: over }), NOW()).request).not.toBeNull();
    expect(validateTrip(draft({ destination: under }), NOW()).errors.destination).toMatch(/mile/);
  });

  it("measures distance as the API does", () => {
    // providers.geo.haversine_mi gives 370.5849 for the same two points.
    expect(haversineMi(DENVER, SALT_LAKE_CITY)).toBeCloseTo(370.5849, 4);
  });
});

describe("request", () => {
  it("is exactly what the API takes", () => {
    expect(validateTrip(draft({ intervalMi: 10 }), NOW()).request).toEqual({
      origin: DENVER,
      destination: SALT_LAKE_CITY,
      departure: "2026-10-19T14:00:00-06:00",
      load_lb: 30_000,
      interval_mi: 10,
    });
  });
});
