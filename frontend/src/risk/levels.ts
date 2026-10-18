/** Risk levels as the API sends them: 0 Low to 4 No Travel, `null` unknown (plan-api D3). */
export type Level = 0 | 1 | 2 | 3 | 4;
export type Rgb = readonly [number, number, number];

export const LEVEL_NAMES = ["Low", "Moderate", "High", "Severe", "No Travel"] as const;

// Ordered green to purple so the scale reads worse left to right, and distinct in hue and
// lightness for colour-blind viewers (ui D6).
export const LEVEL_COLORS: readonly Rgb[] = [
  [46, 158, 91],
  [242, 193, 46],
  [240, 138, 36],
  [217, 58, 58],
  [123, 31, 162],
];
export const UNKNOWN_COLOR: Rgb = [154, 163, 173];

export function levelName(level: number | null): string {
  return level === null ? "Unknown" : (LEVEL_NAMES[level] ?? "Unknown");
}

export function levelColor(level: number | null): Rgb {
  return level === null ? UNKNOWN_COLOR : (LEVEL_COLORS[level] ?? UNKNOWN_COLOR);
}

export function cssColor(rgb: Rgb, alpha = 1): string {
  return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha})`;
}

/** The miles-by-level keys in level order, with unknown last. */
export const MILES_KEYS = ["low", "moderate", "high", "severe", "no_travel", "unknown"] as const;
