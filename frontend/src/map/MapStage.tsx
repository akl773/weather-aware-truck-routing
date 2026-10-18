import type { PickingInfo } from "@deck.gl/core";
import { useCallback, useMemo, useState } from "react";

import type { PlanRequest, PlanResponse } from "../api/client";
import type { components } from "../api/schema";
import { type HeatmapView, blendFrames, frameColors } from "../corridor/colors";
import { cellPolygons, heatmapLayer, truckLayer } from "../corridor/heatmapLayers";
import { Timeline } from "../corridor/Timeline";
import { useCorridor } from "../corridor/useCorridor";
import { MapView } from "./MapView";
import { type CheckpointPick, planBounds, planGeometry, planLayers } from "./planLayers";

type RouteId = components["schemas"]["IdEnum"];

const HOUR_MS = 3_600_000;

interface MapStageProps {
  plan: PlanResponse | undefined;
  planFetchedAt: number;
  request: PlanRequest | null;
  selectedId: RouteId;
  highlighted: CheckpointPick | null;
  onSelectRoute: (id: RouteId) => void;
  onHover: (info: PickingInfo) => void;
  onMoveStart: () => void;
}

/**
 * The map and the timeline. The slider's hour lives here, so scrubbing re-renders only the map
 * layers and the timeline, never the panel (corridor-heatmap D7).
 */
export function MapStage({
  plan,
  planFetchedAt,
  request,
  selectedId,
  highlighted,
  onSelectRoute,
  onHover,
  onMoveStart,
}: MapStageProps) {
  const corridor = useCorridor(plan, request, planFetchedAt);
  const [view, setView] = useState<HeatmapView>("risk");
  // A new plan starts the slider at its departure.
  const [clock, setClock] = useState<{ plan: PlanResponse | undefined; hour: number }>({
    plan,
    hour: 0,
  });
  const hour = clock.plan === plan ? clock.hour : 0;
  const setHour = useCallback((next: number) => setClock({ plan, hour: next }), [plan]);

  const bounds = useMemo(() => (plan ? planBounds(plan) : null), [plan]);
  const geometry = useMemo(
    () => (plan ? planGeometry(plan, selectedId) : null),
    [plan, selectedId],
  );
  const polygons = useMemo(
    () => (corridor.data ? cellPolygons(corridor.data) : null),
    [corridor.data],
  );
  const frames = useMemo(
    () => (corridor.data ? frameColors(corridor.data, view) : null),
    [corridor.data, view],
  );
  const colors = useMemo(
    () => (corridor.data ? new Uint8ClampedArray(corridor.data.cells.length * 4) : null),
    [corridor.data],
  );

  // The same layer instances while scrubbing, so deck.gl skips them without diffing their props.
  const routeLayers = useMemo(
    () =>
      request && geometry
        ? planLayers({ geometry, request, selectedId, highlighted, onSelectRoute })
        : [],
    [geometry, request, selectedId, highlighted, onSelectRoute],
  );

  const layers = [];
  if (polygons && frames && colors) {
    blendFrames(frames, hour, colors);
    layers.push(heatmapLayer({ polygons, colors, hour, view }));
  }
  layers.push(...routeLayers);
  if (plan && request) {
    layers.push(truckLayer(plan, selectedId, Date.parse(request.departure) + hour * HOUR_MS));
  }

  return (
    <>
      <MapView layers={layers} bounds={bounds} onHover={onHover} onMoveStart={onMoveStart} />
      {plan && request ? (
        <Timeline
          start={request.departure}
          hour={hour}
          onHour={setHour}
          view={view}
          onView={setView}
          status={corridor.isError ? "error" : corridor.data ? "ready" : "loading"}
          error={corridor.error?.message ?? null}
          onRetry={() => corridor.refetch()}
        />
      ) : null}
    </>
  );
}
