import Air from "@mui/icons-material/Air";
import AltRoute from "@mui/icons-material/AltRoute";
import WarningAmberRounded from "@mui/icons-material/WarningAmberRounded";
import Alert from "@mui/material/Alert";
import AlertTitle from "@mui/material/AlertTitle";
import Box from "@mui/material/Box";
import ButtonBase from "@mui/material/ButtonBase";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { memo } from "react";

import type { PlanResponse } from "../api/client";
import type { components } from "../api/schema";
import { formatDuration, formatMiles } from "../format";
import { LEVEL_NAMES, MILES_KEYS, cssColor, levelColor } from "../risk/levels";

type Route = components["schemas"]["Route"];
type RouteId = components["schemas"]["IdEnum"];

const MILES_LABELS = [...LEVEL_NAMES, "Unknown"];

/** The recommendation and why, with the one warning that changes what a dispatcher does. */
export const Recommendation = memo(function Recommendation({ plan }: { plan: PlanResponse }) {
  const { recommendation } = plan;
  return (
    <Stack spacing={1.5} role="status">
      {recommendation.all_routes_cross_no_travel ? (
        <Alert severity="error" icon={<WarningAmberRounded />}>
          <AlertTitle>Every route crosses No Travel weather</AlertTitle>
          Route {recommendation.route_id} has the least of it. Consider a later departure.
        </Alert>
      ) : null}
      <Box
        sx={{
          p: 1.75,
          borderRadius: 2,
          bgcolor: "rgba(31, 78, 121, 0.06)",
          border: 1,
          borderColor: "rgba(31, 78, 121, 0.18)",
        }}
      >
        <Typography variant="overline" color="primary" sx={{ lineHeight: 1.6, fontWeight: 700 }}>
          Recommended: Route {recommendation.route_id}
        </Typography>
        <Typography variant="body2">{recommendation.reason}</Typography>
      </Box>
    </Stack>
  );
});

/** Miles at each level as one bar, so the routes compare at a glance. */
function LevelBar({ route }: { route: Route }) {
  const { miles_by_level: miles, distance_mi: total } = route.summary;
  const parts = MILES_KEYS.map((key, i) => ({
    key,
    label: MILES_LABELS[i],
    miles: miles[key],
    color: cssColor(levelColor(key === "unknown" ? null : i)),
  })).filter((part) => part.miles > 0);
  return (
    <Box>
      <Box
        sx={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", bgcolor: "grey.200" }}
        aria-hidden
      >
        {parts.map((part) => (
          // A sliver of Severe or No Travel still shows.
          <Box
            key={part.key}
            sx={{ width: `${(100 * part.miles) / total}%`, minWidth: 3, bgcolor: part.color }}
          />
        ))}
      </Box>
      <Stack direction="row" sx={{ flexWrap: "wrap", columnGap: 1.5, rowGap: 0.25, mt: 0.75 }}>
        {parts.map((part) => (
          <Typography
            key={part.key}
            variant="caption"
            color="text.secondary"
            sx={{ whiteSpace: "nowrap" }}
          >
            <Box
              component="span"
              sx={{
                display: "inline-block",
                width: 8,
                height: 8,
                borderRadius: "50%",
                mr: 0.5,
                bgcolor: part.color,
              }}
            />
            {part.label} {formatMiles(part.miles)}
          </Typography>
        ))}
      </Stack>
    </Box>
  );
}

const VISUALLY_HIDDEN = {
  position: "absolute",
  width: 1,
  height: 1,
  overflow: "hidden",
  clip: "rect(0 0 0 0)",
  whiteSpace: "nowrap",
} as const;

/** The card in one sentence, for screen readers, which read a button's content as its name only. */
function describe(route: Route, recommended: boolean): string {
  const { summary } = route;
  const miles = MILES_KEYS.map((key, i) => [MILES_LABELS[i], summary.miles_by_level[key]] as const)
    .filter(([, mi]) => mi > 0)
    .map(([label, mi]) => `${label} ${formatMiles(mi)}`)
    .join(", ");
  const mean = summary.mean_level === null ? "unknown" : summary.mean_level.toFixed(2);
  return [
    recommended ? "Recommended." : "",
    route.fallback ? "Fallback route." : "",
    `${formatDuration(summary.duration_min)}, ${formatMiles(summary.distance_mi)}.`,
    `${miles}.`,
    `Mean level ${mean} of 4, ${route.checkpoints.length} checkpoints.`,
  ]
    .filter(Boolean)
    .join(" ");
}

interface RouteCardProps {
  route: Route;
  rank: number;
  recommended: boolean;
  selected: boolean;
  onSelect: () => void;
}

function RouteCard({ route, rank, recommended, selected, onSelect }: RouteCardProps) {
  const { summary } = route;
  const detailsId = `route-${route.id}-details`;
  return (
    // A div with the button role, so the card's headings and blocks are valid inside it; the
    // name stays short and the summary is read as its description.
    <ButtonBase
      component="div"
      onClick={onSelect}
      aria-pressed={selected}
      aria-label={`Route ${route.id}, ranked ${rank}`}
      aria-describedby={detailsId}
      sx={{
        display: "block",
        width: "100%",
        textAlign: "left",
        p: 1.75,
        borderRadius: 2,
        border: 2,
        borderColor: selected ? "primary.main" : "divider",
        bgcolor: "background.paper",
        transition: "border-color 120ms",
        "&:hover": { borderColor: selected ? "primary.main" : "grey.400" },
        "&.Mui-focusVisible": { outline: "3px solid", outlineColor: "primary.light" },
      }}
    >
      <Stack direction="row" sx={{ alignItems: "center", mb: 1.25 }} spacing={1}>
        <Box
          sx={{
            display: "grid",
            placeItems: "center",
            width: 26,
            height: 26,
            borderRadius: "50%",
            fontWeight: 700,
            fontSize: 13,
            bgcolor: selected ? "primary.main" : "grey.200",
            color: selected ? "primary.contrastText" : "text.primary",
          }}
        >
          {route.id}
        </Box>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Route {route.id}
        </Typography>
        {recommended ? (
          <Chip label="Recommended" size="small" color="success" sx={{ height: 20 }} />
        ) : null}
        {route.fallback ? (
          <Tooltip title="A fallback route: found by sending the router through a point off the direct line, to offer a third distinct route.">
            <Chip
              icon={<AltRoute />}
              label="Fallback"
              size="small"
              variant="outlined"
              sx={{ height: 20 }}
            />
          </Tooltip>
        ) : null}
        <Box sx={{ flex: 1 }} />
        <Box sx={{ textAlign: "right" }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
            {formatDuration(summary.duration_min)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {formatMiles(summary.distance_mi)}
          </Typography>
        </Box>
      </Stack>
      <LevelBar route={route} />
      <Stack direction="row" spacing={2} sx={{ mt: 1 }}>
        <Typography variant="caption" color="text.secondary">
          #{rank} by risk
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Mean level{" "}
          <Box component="span" sx={{ color: "text.primary", fontWeight: 600 }}>
            {summary.mean_level === null ? "unknown" : summary.mean_level.toFixed(2)}
          </Box>{" "}
          of 4
        </Typography>
        <Typography variant="caption" color="text.secondary">
          <Air sx={{ fontSize: 12, verticalAlign: "-2px", mr: 0.25 }} />
          {route.checkpoints.length} checkpoints
        </Typography>
      </Stack>
      <Box component="span" id={detailsId} sx={VISUALLY_HIDDEN}>
        {describe(route, recommended)}
      </Box>
    </ButtonBase>
  );
}

interface RouteCardsProps {
  plan: PlanResponse;
  selectedId: RouteId;
  onSelect: (id: RouteId) => void;
}

/** The routes in ranked order; choosing one selects it on the map too (ui D7). */
export const RouteCards = memo(function RouteCards({ plan, selectedId, onSelect }: RouteCardsProps) {
  const byId = new Map(plan.routes.map((route) => [route.id, route]));
  return (
    <Stack spacing={1.25} component="section" aria-label="Routes, best first">
      {plan.recommendation.ranking.map((id, i) => {
        const route = byId.get(id);
        return route ? (
          <RouteCard
            key={id}
            route={route}
            rank={i + 1}
            recommended={id === plan.recommendation.route_id}
            selected={id === selectedId}
            onSelect={() => onSelect(id)}
          />
        ) : null;
      })}
    </Stack>
  );
});
