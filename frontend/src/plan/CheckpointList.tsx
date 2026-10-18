import ExpandLess from "@mui/icons-material/ExpandLess";
import ExpandMore from "@mui/icons-material/ExpandMore";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Collapse from "@mui/material/Collapse";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { type KeyboardEvent, memo, useState } from "react";

import type { components } from "../api/schema";
import { formatReading, formatTime } from "../format";
import { LevelChip, levelReason } from "./CheckpointDetails";

type Route = components["schemas"]["Route"];

interface CheckpointListProps {
  route: Route;
  onHighlight: (index: number | null) => void;
}

/**
 * Every checkpoint of the selected route, readable without the map (#13 acceptance). The list is
 * one tab stop; the arrow keys move between rows, as in a listbox.
 */
export const CheckpointList = memo(function CheckpointList({ route, onHighlight }: CheckpointListProps) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const last = route.checkpoints.length - 1;
  const current = Math.min(active, last);

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    const moves: Record<string, number> = {
      ArrowDown: current + 1,
      ArrowUp: current - 1,
      Home: 0,
      End: last,
    };
    const next = moves[event.key];
    if (next === undefined) return;
    event.preventDefault();
    const target = Math.max(0, Math.min(last, next));
    setActive(target);
    event.currentTarget.querySelectorAll<HTMLElement>("li")[target]?.focus();
  };

  return (
    <Box>
      <Button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls="checkpoint-list"
        endIcon={open ? <ExpandLess /> : <ExpandMore />}
        size="small"
        sx={{ px: 0.5 }}
      >
        {open ? "Hide" : "Show"} {route.checkpoints.length} checkpoints on Route {route.id}
      </Button>
      <Collapse in={open} unmountOnExit>
        <Box
          id="checkpoint-list"
          component="ol"
          aria-label={`Checkpoints on Route ${route.id}`}
          onMouseLeave={() => onHighlight(null)}
          onKeyDown={onKeyDown}
          sx={{ listStyle: "none", m: 0, mt: 0.5, p: 0, border: 1, borderColor: "divider", borderRadius: 2 }}
        >
          {route.checkpoints.map((checkpoint, i) => {
            const { readings } = checkpoint;
            const reason = levelReason(checkpoint);
            return (
              <Box
                component="li"
                key={checkpoint.mile}
                tabIndex={i === current ? 0 : -1}
                onMouseEnter={() => onHighlight(i)}
                onFocus={() => {
                  setActive(i);
                  onHighlight(i);
                }}
                onBlur={() => onHighlight(null)}
                sx={{
                  px: 1.5,
                  py: 1,
                  borderTop: i === 0 ? 0 : 1,
                  borderColor: "divider",
                  outline: "none",
                  "&:hover, &:focus-visible": { bgcolor: "action.hover" },
                }}
              >
                <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between" }}>
                  <Typography variant="body2" sx={{ fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
                    Mile {checkpoint.mile.toFixed(1)}
                    <Typography component="span" variant="body2" color="text.secondary">
                      {" · "}
                      {formatTime(checkpoint.eta)}
                    </Typography>
                  </Typography>
                  <LevelChip level={checkpoint.level} />
                </Stack>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: "block", fontVariantNumeric: "tabular-nums" }}
                >
                  Wind {formatReading(readings.wind_mph, 1, "mph")}
                  {readings.gust_mph === null ? "" : ` (gusts ${readings.gust_mph.toFixed(1)})`}
                  {" · "}Rain {formatReading(readings.rain_in_hr, 2, "in/hr")}
                  {" · "}Snow {formatReading(readings.snow_in_hr, 2, "in/hr")}
                </Typography>
                {reason || checkpoint.gusty ? (
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
                    {reason}
                    {checkpoint.gusty ? " Gusty." : ""}
                  </Typography>
                ) : null}
              </Box>
            );
          })}
        </Box>
      </Collapse>
    </Box>
  );
});
