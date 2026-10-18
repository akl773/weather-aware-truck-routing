import type { CorridorResponse } from "../api/client";
import { LEVEL_COLORS, UNKNOWN_COLOR } from "../risk/levels";

export type HeatmapView = "risk" | "wind" | "rain" | "snow";

type Rgba = readonly [number, number, number, number];
type Frame = CorridorResponse["frames"][number];

/** A reading's ramp: stops of value and colour, full strength at its No Travel threshold (corridor-heatmap D6). */
interface Ramp {
  unit: string;
  field: "wind_mph" | "rain_in_hr" | "snow_in_hr";
  stops: readonly (readonly [number, Rgba])[];
}

// Low is faintest so the eye goes to the weather that matters (corridor-heatmap D6).
const LEVEL_ALPHA = [70, 120, 140, 155, 175];
const UNKNOWN: Rgba = [...UNKNOWN_COLOR, 60];

export const RAMPS: Record<Exclude<HeatmapView, "risk">, Ramp> = {
  wind: {
    unit: "mph",
    field: "wind_mph",
    stops: [
      [0, [191, 211, 230, 0]],
      [15, [158, 188, 218, 90]],
      [30, [140, 107, 177, 140]],
      [45, [136, 65, 157, 165]],
      [55, [110, 1, 107, 185]],
    ],
  },
  rain: {
    unit: "in/hr",
    field: "rain_in_hr",
    stops: [
      [0, [158, 202, 225, 0]],
      [0.02, [158, 202, 225, 80]],
      [0.1, [66, 146, 198, 130]],
      [0.25, [33, 113, 181, 155]],
      [0.5, [8, 81, 156, 170]],
      [1, [8, 48, 107, 190]],
    ],
  },
  snow: {
    unit: "in/hr",
    field: "snow_in_hr",
    stops: [
      [0, [168, 221, 181, 0]],
      [0.1, [168, 221, 181, 90]],
      [0.5, [123, 204, 196, 130]],
      [1, [67, 162, 202, 155]],
      [2, [8, 104, 172, 170]],
      [3, [8, 64, 129, 190]],
    ],
  },
};

/** The ramp's colour at `value`, linear between stops and held past the last. */
export function rampColor(ramp: Ramp, value: number): Rgba {
  const { stops } = ramp;
  const first = stops[0] as (typeof stops)[number];
  if (value <= first[0]) return first[1];
  for (let i = 1; i < stops.length; i++) {
    const [hi, top] = stops[i] as (typeof stops)[number];
    if (value <= hi) {
      const [lo, bottom] = stops[i - 1] as (typeof stops)[number];
      const t = (value - lo) / (hi - lo);
      return bottom.map((c, k) => Math.round(c + ((top[k] as number) - c) * t)) as unknown as Rgba;
    }
  }
  return (stops[stops.length - 1] as (typeof stops)[number])[1];
}

export function levelFill(level: number | null): Rgba {
  if (level === null) return UNKNOWN;
  const rgb = LEVEL_COLORS[level];
  return rgb ? [...rgb, LEVEL_ALPHA[level] as number] : UNKNOWN;
}

function cellColor(frame: Frame, view: HeatmapView, cell: number): Rgba {
  if (view === "risk") return levelFill(frame.level[cell] ?? null);
  const ramp = RAMPS[view];
  const value = frame[ramp.field][cell];
  return value === null || value === undefined ? UNKNOWN : rampColor(ramp, value);
}

/** Every frame's RGBA bytes for one view, computed once per corridor (corridor-heatmap D7). */
export function frameColors(corridor: CorridorResponse, view: HeatmapView): Uint8ClampedArray[] {
  const cells = corridor.cells.length;
  return corridor.frames.map((frame) => {
    const bytes = new Uint8ClampedArray(cells * 4);
    for (let cell = 0; cell < cells; cell++) bytes.set(cellColor(frame, view, cell), cell * 4);
    return bytes;
  });
}

/** Frames blended at `hour` into `out`: hour 2.25 is a quarter of the way from frame 2 to 3. */
export function blendFrames(frames: Uint8ClampedArray[], hour: number, out: Uint8ClampedArray) {
  const last = frames.length - 1;
  const clamped = Math.min(Math.max(hour, 0), last);
  const lo = Math.floor(clamped);
  const a = frames[lo] as Uint8ClampedArray;
  const b = frames[Math.min(lo + 1, last)] as Uint8ClampedArray;
  const t = clamped - lo;
  for (let i = 0; i < out.length; i++)
    out[i] = (a[i] as number) + ((b[i] as number) - (a[i] as number)) * t;
  return out;
}
