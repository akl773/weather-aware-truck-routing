import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import type { components } from "../api/schema";
import { formatReading, formatTime } from "../format";
import { cssColor, levelColor, levelName } from "../risk/levels";

type Checkpoint = components["schemas"]["Checkpoint"];

export function LevelChip({ level }: { level: number | null }) {
  const color = levelColor(level);
  return (
    <Box
      component="span"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        gap: 0.5,
        px: 0.75,
        py: 0.125,
        borderRadius: 1,
        fontSize: 12,
        fontWeight: 600,
        whiteSpace: "nowrap",
        bgcolor: cssColor(color, 0.16),
        color: level === null ? "text.secondary" : "text.primary",
      }}
    >
      <Box
        component="span"
        sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: cssColor(color) }}
      />
      {levelName(level)}
    </Box>
  );
}

/** A driver condition with its reading, as CONTEXT.md writes it: "snow 2.40 in/hr". */
function driverReading(driver: Checkpoint["drivers"][number], readings: Checkpoint["readings"]) {
  if (driver === "wind") return `wind ${formatReading(readings.wind_mph, 1, "mph")}`;
  if (driver === "rain") return `rain ${formatReading(readings.rain_in_hr, 2, "in/hr")}`;
  return `snow ${formatReading(readings.snow_in_hr, 2, "in/hr")}`;
}

/** Why a checkpoint has its level, in a sentence. */
export function levelReason(checkpoint: Checkpoint): string {
  if (checkpoint.level === null) return "No full forecast at this ETA.";
  if (checkpoint.drivers.length === 0) return "";
  const drivers = checkpoint.drivers.map((d) => driverReading(d, checkpoint.readings));
  return `Set by ${drivers.join(" and ")}.`;
}

/** Everything the API says about one checkpoint (spec: ETA, values, level, driver). */
export function CheckpointDetails({ routeId, checkpoint }: { routeId: string; checkpoint: Checkpoint }) {
  const { readings } = checkpoint;
  const rows: [string, string][] = [
    [
      "Wind",
      `${formatReading(readings.wind_mph, 1, "mph")}${
        readings.gust_mph === null ? "" : `, gusts ${formatReading(readings.gust_mph, 1, "mph")}`
      }`,
    ],
    ["Rain", formatReading(readings.rain_in_hr, 2, "in/hr")],
    ["Snow", formatReading(readings.snow_in_hr, 2, "in/hr")],
  ];
  return (
    <Stack spacing={0.75} sx={{ minWidth: 220 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center", justifyContent: "space-between" }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Route {routeId} · mile {checkpoint.mile.toFixed(1)}
        </Typography>
        <LevelChip level={checkpoint.level} />
      </Stack>
      <Typography variant="body2" color="text.secondary">
        ETA {formatTime(checkpoint.eta)}
      </Typography>
      <Box component="dl" sx={{ m: 0, display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 1.5 }}>
        {rows.map(([name, value]) => (
          <Box key={name} sx={{ display: "contents" }}>
            <Typography component="dt" variant="body2" color="text.secondary">
              {name}
            </Typography>
            <Typography component="dd" variant="body2" sx={{ m: 0, fontVariantNumeric: "tabular-nums" }}>
              {value}
            </Typography>
          </Box>
        ))}
      </Box>
      <Typography variant="caption" color="text.secondary">
        Readings are rounded. Risk uses the unrounded forecast.
      </Typography>
      {levelReason(checkpoint) || checkpoint.gusty ? (
        <Typography variant="caption" color="text.secondary">
          {levelReason(checkpoint)}
          {checkpoint.gusty ? " Gusts reach a higher band than the wind." : ""}
        </Typography>
      ) : null}
    </Stack>
  );
}
