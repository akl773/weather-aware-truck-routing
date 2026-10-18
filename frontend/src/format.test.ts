import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { formatDuration, formatMiles, formatReading, formatTime } from "./format";

const ORIGINAL_TZ = process.env.TZ;
beforeEach(() => {
  process.env.TZ = "America/Denver";
});
afterEach(() => {
  process.env.TZ = ORIGINAL_TZ;
});

describe("formatting (ui D3, recommendation D4)", () => {
  it("shows times in the browser's zone", () => {
    expect(formatTime("2026-10-19T20:05:00Z")).toBe("Mon 2:05 PM");
  });

  it("writes durations in hours and minutes", () => {
    expect(formatDuration(443)).toBe("7 h 23 min");
    expect(formatDuration(45)).toBe("45 min");
    expect(formatDuration(120)).toBe("2 h 0 min");
  });

  it("pads miles the API rounded without rounding them again", () => {
    expect(formatMiles(1023.3)).toBe("1,023.3 mi");
    expect(formatMiles(3)).toBe("3.0 mi");
  });

  it("pads readings and marks unknown ones", () => {
    expect(formatReading(0.1, 2, "in/hr")).toBe("0.10 in/hr");
    expect(formatReading(null, 1, "mph")).toBe("—");
  });
});
