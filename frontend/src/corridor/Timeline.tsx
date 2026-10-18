import Pause from "@mui/icons-material/Pause";
import PlayArrow from "@mui/icons-material/PlayArrow";
import Replay from "@mui/icons-material/Replay";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import IconButton from "@mui/material/IconButton";
import LinearProgress from "@mui/material/LinearProgress";
import Paper from "@mui/material/Paper";
import Slider from "@mui/material/Slider";
import Stack from "@mui/material/Stack";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { type Ref, memo, useEffect, useMemo, useState } from "react";

import { formatDuration, formatTime } from "../format";
import { LEVEL_NAMES } from "../risk/levels";
import { type HeatmapView, RAMPS, UNKNOWN_FILL, levelFill, rampColor } from "./colors";

export const HOURS = 48;
const HOUR_MS = 3_600_000;
// Play runs the 48 hours in 16 seconds (corridor-heatmap D7).
const PLAY_HOURS_PER_MS = HOURS / 16_000;
// A frame after a stall (a background tab, a long task) moves Play on by at most this much.
const MAX_FRAME_MS = 100;
const MARKS = [0, 12, 24, 36, 48];

const VIEWS: { value: HeatmapView; label: string }[] = [
  { value: "risk", label: "Risk" },
  { value: "wind", label: "Wind" },
  { value: "rain", label: "Rain" },
  { value: "snow", label: "Snow" },
];

function shortTime(at: Date) {
  return new Intl.DateTimeFormat("en-US", { weekday: "short", hour: "numeric" }).format(at);
}

/** The slider's step: Play passes through every value, but times are told to the quarter hour. */
function quarter(hour: number) {
  return Math.round(hour * 4) / 4;
}

function afterDeparture(hour: number) {
  return hour === 0 ? "at departure" : `${formatDuration(hour * 60)} after departure`;
}

type Rgba = readonly [number, number, number, number];

/** A map colour shown over white at half again its strength, so the faintest still shows. */
function legendColor([r, g, b, a]: Rgba) {
  return `rgba(${r}, ${g}, ${b}, ${Math.min(1, (a / 255) * 1.5)})`;
}

function Swatch({ color }: { color: string }) {
  return (
    <Box
      component="span"
      sx={{
        display: "inline-block",
        width: 10,
        height: 10,
        borderRadius: 0.5,
        mr: 0.5,
        bgcolor: color,
      }}
    />
  );
}

/** What the colours mean in the current view (corridor-heatmap D6). */
const Legend = memo(function Legend({ view }: { view: HeatmapView }) {
  if (view === "risk") {
    return (
      <Stack direction="row" sx={{ flexWrap: "wrap", columnGap: 1.5, rowGap: 0.25 }}>
        {[...LEVEL_NAMES, "Unknown"].map((name, level) => (
          <Typography
            key={name}
            variant="caption"
            color="text.secondary"
            sx={{ whiteSpace: "nowrap" }}
          >
            <Swatch color={legendColor(levelFill(name === "Unknown" ? null : level))} />
            {name}
          </Typography>
        ))}
      </Stack>
    );
  }
  const ramp = RAMPS[view];
  const top = ramp.stops.at(-1)?.[0] ?? 1;
  const gradient = ramp.stops
    .map(([value]) => `${legendColor(rampColor(ramp, value))} ${(100 * value) / top}%`)
    .join(", ");
  return (
    <Stack
      direction="row"
      spacing={1}
      sx={{ width: "100%", maxWidth: 360, alignItems: "flex-start" }}
    >
      <Box sx={{ flex: 1 }}>
        <Box
          aria-hidden
          sx={{
            height: 8,
            borderRadius: 4,
            border: 1,
            borderColor: "divider",
            background: `linear-gradient(to right, ${gradient})`,
          }}
        />
        <Box sx={{ position: "relative", height: 16 }}>
          {ramp.ticks.map((value, i) => {
            const last = i === ramp.ticks.length - 1;
            return (
              <Typography
                key={value}
                variant="caption"
                color="text.secondary"
                sx={{
                  position: "absolute",
                  left: `${(100 * value) / top}%`,
                  transform: last ? "translateX(-100%)" : "translateX(-50%)",
                  whiteSpace: "nowrap",
                  fontSize: 11,
                }}
              >
                {value}
                {last ? "+" : ""}
              </Typography>
            );
          })}
        </Box>
      </Box>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ lineHeight: "8px", whiteSpace: "nowrap" }}
      >
        {ramp.unit}
      </Typography>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ lineHeight: "8px", whiteSpace: "nowrap", pl: 1 }}
      >
        <Swatch color={legendColor(UNKNOWN_FILL)} />
        Unknown
      </Typography>
    </Stack>
  );
});

const ViewToggle = memo(function ViewToggle({
  view,
  onView,
}: {
  view: HeatmapView;
  onView: (view: HeatmapView) => void;
}) {
  return (
    <ToggleButtonGroup
      exclusive
      size="small"
      value={view}
      onChange={(_, next: HeatmapView | null) => next && onView(next)}
      aria-label="Heatmap view"
    >
      {VIEWS.map((v) => (
        <ToggleButton key={v.value} value={v.value} sx={{ px: { xs: 0.75, sm: 1.25 }, py: 0.25 }}>
          {v.label}
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  );
});

interface TimelineProps {
  /** The departure, hour 0. */
  start: string;
  hour: number;
  onHour: (hour: number) => void;
  view: HeatmapView;
  onView: (view: HeatmapView) => void;
  status: "loading" | "ready" | "error";
  error: string | null;
  onRetry: () => void;
  /** The panel, for measuring how much of the map it covers. */
  ref?: Ref<HTMLElement>;
}

/** The 48 hours after departure: the slider, Play, the view and its legend (corridor-heatmap D7). */
export function Timeline({
  start,
  hour,
  onHour,
  view,
  onView,
  status,
  error,
  onRetry,
  ref,
}: TimelineProps) {
  // The hour Play started from; null while paused.
  const [playFrom, setPlayFrom] = useState<number | null>(null);
  const departure = Date.parse(start);
  const at = new Date(departure + hour * HOUR_MS);

  useEffect(() => {
    if (playFrom === null) return;
    let current = playFrom;
    let last = performance.now();
    let frame = requestAnimationFrame(function tick(now) {
      current = Math.min(HOURS, current + Math.min(now - last, MAX_FRAME_MS) * PLAY_HOURS_PER_MS);
      last = now;
      onHour(current);
      if (current >= HOURS) setPlayFrom(null);
      else frame = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(frame);
  }, [playFrom, onHour]);

  const marks = useMemo(
    () => MARKS.map((h) => ({ value: h, label: shortTime(new Date(departure + h * HOUR_MS)) })),
    [departure],
  );

  const playing = playFrom !== null;
  const togglePlay = () => {
    if (!playing) return setPlayFrom(hour >= HOURS ? 0 : hour);
    // Paused on a value the slider can step from.
    setPlayFrom(null);
    onHour(quarter(hour));
  };

  return (
    <Paper
      ref={ref}
      component="section"
      aria-label="Forecast timeline"
      elevation={0}
      sx={{
        position: "absolute",
        zIndex: 2,
        left: { xs: 8, md: 432 },
        right: { xs: 8, md: 64 },
        // Above the attribution and the build stamp on narrow screens.
        bottom: { xs: 36, md: 16 },
        maxWidth: 880,
        px: 2,
        pt: 1.25,
        pb: 1,
        borderRadius: 3,
        border: 1,
        borderColor: "divider",
        boxShadow: "0 8px 32px rgba(15, 23, 42, 0.12)",
        // Its own compositor layer: the text and thumb change every Play frame, the map beneath does not.
        willChange: "transform",
      }}
    >
      <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
        <Tooltip title={playing ? "Pause" : "Play the next 48 hours"}>
          <IconButton
            onClick={togglePlay}
            aria-label={playing ? "Pause" : "Play"}
            sx={{
              bgcolor: "primary.main",
              color: "primary.contrastText",
              "&:hover": { bgcolor: "primary.dark" },
            }}
            size="small"
          >
            {playing ? <Pause fontSize="small" /> : <PlayArrow fontSize="small" />}
          </IconButton>
        </Tooltip>
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography
            variant="subtitle2"
            sx={{ fontWeight: 700, lineHeight: 1.25 }}
            aria-live="off"
          >
            {formatTime(at)}
          </Typography>
          <Typography variant="caption" color="text.secondary" noWrap component="p">
            {afterDeparture(quarter(hour))}
          </Typography>
        </Box>
        <ViewToggle view={view} onView={onView} />
      </Stack>

      {/* Room for the end marks' labels, which centre on the slider's ends. */}
      <Box sx={{ px: 3 }}>
        <Slider
          aria-label="Hours after departure"
          min={0}
          max={HOURS}
          step={0.25}
          shiftStep={3}
          value={hour}
          onChange={(_, value) => {
            setPlayFrom(null);
            onHour(value);
          }}
          marks={marks}
          getAriaValueText={(h) =>
            `${formatTime(new Date(departure + quarter(h) * HOUR_MS))}, ${afterDeparture(quarter(h))}`
          }
          size="small"
          sx={{
            "& .MuiSlider-markLabel": { fontSize: 11, color: "text.secondary" },
            // The thumb follows Play every frame; an easing transition would trail behind it.
            "& .MuiSlider-thumb, & .MuiSlider-track": { transition: "none" },
          }}
        />
      </Box>

      <Box sx={{ minHeight: 22, display: "flex", alignItems: "center" }}>
        {status === "loading" ? (
          <Box sx={{ width: "100%" }} role="status">
            <Typography variant="caption" color="text.secondary">
              Loading the corridor's weather for the next 48 hours…
            </Typography>
            <LinearProgress sx={{ mt: 0.5, height: 3, borderRadius: 2 }} />
          </Box>
        ) : status === "error" ? (
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            <Typography variant="caption" color="error" role="alert">
              {error ?? "The corridor's weather could not be loaded."}
            </Typography>
            <Button size="small" startIcon={<Replay />} onClick={onRetry}>
              Retry
            </Button>
          </Stack>
        ) : (
          <Legend view={view} />
        )}
      </Box>
    </Paper>
  );
}
