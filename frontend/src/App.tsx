import type { PickingInfo } from "@deck.gl/core";
import Box from "@mui/material/Box";
import Collapse from "@mui/material/Collapse";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { type PlanRequest, fetchHealth } from "./api/client";
import type { components } from "./api/schema";
import { Header } from "./layout/Header";
import { Panel } from "./layout/Panel";
import { CheckpointTooltip } from "./map/CheckpointTooltip";
import { MapView } from "./map/MapView";
import { type CheckpointPick, planBounds, planLayers } from "./map/planLayers";
import { CheckpointList } from "./plan/CheckpointList";
import { Recommendation, RouteCards } from "./plan/RouteCards";
import { usePlan } from "./plan/usePlan";
import { TripForm } from "./trip/TripForm";
import { TripSummary } from "./trip/TripSummary";

type RouteId = components["schemas"]["IdEnum"];

interface Hover {
  pick: CheckpointPick;
  x: number;
  y: number;
}

export function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => fetchHealth() });
  const [request, setRequest] = useState<PlanRequest | null>(null);
  const [editing, setEditing] = useState(true);
  const plan = usePlan(request);
  const data = plan.data;

  // A new plan starts on its recommended route (ui D7).
  const [chosen, setChosen] = useState<{ plan: unknown; id: RouteId } | null>(null);
  const selectedId =
    data && chosen?.plan === data ? chosen.id : (data?.recommendation.route_id ?? "A");
  const select = (id: RouteId) => data && setChosen({ plan: data, id });

  const [hover, setHover] = useState<Hover | null>(null);
  const [listed, setListed] = useState<number | null>(null);
  const selectedRoute = data?.routes.find((route) => route.id === selectedId);
  const highlighted =
    listed !== null && selectedRoute?.checkpoints[listed]
      ? { routeId: selectedId, index: listed, checkpoint: selectedRoute.checkpoints[listed] }
      : (hover?.pick ?? null);

  const bounds = useMemo(() => (data ? planBounds(data) : null), [data]);
  const layers = data && request
    ? planLayers({ plan: data, request, selectedId, highlighted, onSelectRoute: select })
    : [];

  const onHover = (info: PickingInfo) => {
    const object = info.object as Partial<CheckpointPick> | undefined;
    setHover(
      info.layer?.id === "checkpoints" && object?.checkpoint
        ? { pick: object as CheckpointPick, x: info.x, y: info.y }
        : null,
    );
  };

  const showResults = Boolean(data) && !editing;

  return (
    <Box sx={{ position: "fixed", inset: 0 }}>
      <Panel>
        <Header />
        <Collapse in={showResults} unmountOnExit>
          {request ? <TripSummary request={request} onEdit={() => setEditing(true)} /> : null}
        </Collapse>
        <Collapse in={!showResults}>
          <TripForm
            onSubmit={(next) => {
              // Asking again for a plan that failed or has gone stale fetches it; the query would not.
              const same = JSON.stringify(next) === JSON.stringify(request);
              if (same && (plan.isError || plan.isStale)) plan.refetch();
              setRequest(next);
              setEditing(false);
            }}
            pending={plan.isFetching}
            error={plan.error?.message ?? null}
          />
        </Collapse>
        {showResults && data && selectedRoute ? (
          <Stack spacing={2} sx={{ mt: 2 }}>
            <Divider />
            <Recommendation plan={data} />
            <RouteCards plan={data} selectedId={selectedId} onSelect={select} />
            <CheckpointList route={selectedRoute} onHighlight={setListed} />
          </Stack>
        ) : null}
      </Panel>
      {/* After the panel, so keyboard users reach the form before the map. */}
      <MapView layers={layers} bounds={bounds} onHover={onHover} />
      {hover ? <CheckpointTooltip pick={hover.pick} x={hover.x} y={hover.y} /> : null}
      <Typography
        component="footer"
        variant="caption"
        color="text.secondary"
        sx={{ position: "absolute", left: 8, bottom: 4, pointerEvents: "none" }}
      >
        {health.data ? `build ${health.data.version}` : "API unreachable"}
      </Typography>
    </Box>
  );
}
