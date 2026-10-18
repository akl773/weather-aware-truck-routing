import { describe, expect, it } from "vitest";

import type { CorridorResponse } from "../api/client";
import { LEVEL_COLORS } from "../risk/levels";
import { RAMPS, blendFrames, frameColors, levelFill, rampColor } from "./colors";

function frame(hour: number, level: (number | null)[], wind: (number | null)[]) {
  return {
    hour,
    level,
    wind_mph: wind,
    gust_mph: wind,
    rain_in_hr: wind.map(() => 0),
    snow_in_hr: wind.map(() => 0),
  };
}

const CORRIDOR: CorridorResponse = {
  cell_deg: 0.3,
  cells: [
    [-105, 40],
    [-104.7, 40],
  ],
  start: "2026-10-19T12:00:00Z",
  frames: [frame(0, [0, null], [10, null]), frame(1, [4, 2], [60, 30])],
};

describe("risk view (corridor-heatmap D6)", () => {
  it("uses the level's colour, Low faintest", () => {
    const [low, noTravel] = [levelFill(0), levelFill(4)];
    expect(low.slice(0, 3)).toEqual([...(LEVEL_COLORS[0] as number[])]);
    expect(low[3]).toBeLessThan(noTravel[3]);
  });

  it("colours unknown cells grey", () => {
    const [bytes] = frameColors(CORRIDOR, "risk");
    expect([...(bytes as Uint8ClampedArray).slice(4, 8)]).toEqual([...levelFill(null)]);
  });
});

describe("reading ramps (corridor-heatmap D6)", () => {
  it("is clear at zero and full strength at the No Travel threshold", () => {
    expect(rampColor(RAMPS.wind, 0)[3]).toBe(0);
    expect(rampColor(RAMPS.wind, 55)).toEqual(RAMPS.wind.stops.at(-1)?.[1]);
    expect(rampColor(RAMPS.rain, 1)).toEqual(RAMPS.rain.stops.at(-1)?.[1]);
    expect(rampColor(RAMPS.snow, 3)).toEqual(RAMPS.snow.stops.at(-1)?.[1]);
  });

  it("holds the last colour past the threshold", () => {
    expect(rampColor(RAMPS.wind, 80)).toEqual(rampColor(RAMPS.wind, 55));
  });

  it("is linear between stops", () => {
    expect(rampColor(RAMPS.wind, 22.5)).toEqual([149, 148, 198, 115]);
  });
});

describe("blendFrames (corridor-heatmap D7)", () => {
  const frames = [new Uint8ClampedArray([0, 100, 200, 40]), new Uint8ClampedArray([100, 100, 0, 80])];

  it("returns a frame exactly on its hour", () => {
    expect([...blendFrames(frames, 1, new Uint8ClampedArray(4))]).toEqual([100, 100, 0, 80]);
  });

  it("mixes the frames either side of a fractional hour", () => {
    expect([...blendFrames(frames, 0.25, new Uint8ClampedArray(4))]).toEqual([25, 100, 150, 50]);
  });

  it("clamps hours outside the frames", () => {
    expect([...blendFrames(frames, -2, new Uint8ClampedArray(4))]).toEqual([0, 100, 200, 40]);
    expect([...blendFrames(frames, 9, new Uint8ClampedArray(4))]).toEqual([100, 100, 0, 80]);
  });
});
