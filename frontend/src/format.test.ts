import { describe, expect, it } from "vitest";

import { formatDuration, formatMiles, formatReading, formatTime } from "./format";

describe("formatting (ui D3, recommendation D4)", () => {
  // The browser's zone is America/Denver in every test (vite.config.ts).
  it("shows times in the browser's zone, with the date", () => {
    expect(formatTime("2026-10-19T20:05:00Z")).toBe("Mon, Oct 19, 2:05 PM");
  });

  it("writes durations in hours and minutes", () => {
    expect(formatDuration(443)).toBe("7 h 23 min");
    expect(formatDuration(45)).toBe("45 min");
    expect(formatDuration(120)).toBe("2 h");
    // Rounded before splitting, so the minutes never read 60.
    expect(formatDuration(119.7)).toBe("2 h");
    expect(formatDuration(59.6)).toBe("1 h");
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
