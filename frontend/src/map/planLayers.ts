import type { Layer, PickingInfo } from "@deck.gl/core";
import { PathLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";

import type { PlanRequest, PlanResponse } from "../api/client";
import type { components } from "../api/schema";
import { type Segment, pointAtMile, routeSegments } from "../plan/segments";
import { levelColor } from "../risk/levels";

type RouteId = components["schemas"]["IdEnum"];
type Checkpoint = components["schemas"]["Checkpoint"];

export interface CheckpointPick {
  routeId: RouteId;
  index: number;
  checkpoint: Checkpoint;
}

interface PlanLayerProps {
  plan: PlanResponse;
  request: PlanRequest;
  selectedId: RouteId;
  highlighted: CheckpointPick | null;
  onSelectRoute: (id: RouteId) => void;
}

const WHITE: [number, number, number] = [255, 255, 255];
const INK: [number, number, number] = [31, 41, 55];
// Routes not selected stay visible for comparison but recede (ui D6).
const DIMMED_ALPHA = 120;

/** The selected route's pieces last, so it draws over the others. */
function selectedLast<T extends { routeId: RouteId }>(items: T[], selectedId: RouteId): T[] {
  return [...items].sort((a, b) => Number(a.routeId === selectedId) - Number(b.routeId === selectedId));
}

export function planLayers({
  plan,
  request,
  selectedId,
  highlighted,
  onSelectRoute,
}: PlanLayerProps): Layer[] {
  const segments = selectedLast(plan.routes.flatMap(routeSegments), selectedId);
  const checkpoints = selectedLast(
    plan.routes.flatMap((route) =>
      route.checkpoints.map((checkpoint, index) => ({ routeId: route.id, index, checkpoint })),
    ),
    selectedId,
  );
  const labels = plan.routes.map((route) => ({
    routeId: route.id,
    position: pointAtMile(route, route.summary.distance_mi / 2),
  }));
  const isSelected = (id: RouteId) => id === selectedId;
  const select = (info: PickingInfo<{ routeId: RouteId }>) => {
    if (info.object) onSelectRoute(info.object.routeId);
    return true;
  };

  return [
    new PathLayer<Segment>({
      id: "route-casing",
      data: segments,
      getPath: (s) => s.path,
      getColor: (s) => (isSelected(s.routeId) ? WHITE : [255, 255, 255, DIMMED_ALPHA]),
      getWidth: (s) => (isSelected(s.routeId) ? 10 : 6),
      widthUnits: "pixels",
      capRounded: true,
      jointRounded: true,
      updateTriggers: { getColor: selectedId, getWidth: selectedId },
    }),
    new PathLayer<Segment>({
      id: "route-level",
      data: segments,
      getPath: (s) => s.path,
      getColor: (s) => [...levelColor(s.level), isSelected(s.routeId) ? 255 : DIMMED_ALPHA],
      getWidth: (s) => (isSelected(s.routeId) ? 6 : 3.5),
      widthUnits: "pixels",
      capRounded: true,
      jointRounded: true,
      pickable: true,
      onClick: select,
      updateTriggers: { getColor: selectedId, getWidth: selectedId },
    }),
    new ScatterplotLayer<CheckpointPick>({
      id: "checkpoints",
      data: checkpoints,
      getPosition: (c) => [c.checkpoint.lon, c.checkpoint.lat],
      getFillColor: (c) => [...levelColor(c.checkpoint.level), isSelected(c.routeId) ? 255 : 150],
      getLineColor: (c) => (isSelected(c.routeId) ? WHITE : [255, 255, 255, 150]),
      getRadius: (c) =>
        highlighted && highlighted.routeId === c.routeId && highlighted.index === c.index
          ? 9
          : isSelected(c.routeId)
            ? 5.5
            : 3,
      radiusUnits: "pixels",
      lineWidthUnits: "pixels",
      getLineWidth: 1.5,
      stroked: true,
      pickable: true,
      onClick: select,
      updateTriggers: {
        getFillColor: selectedId,
        getLineColor: selectedId,
        getRadius: [selectedId, highlighted?.routeId, highlighted?.index],
      },
    }),
    new ScatterplotLayer({
      id: "trip-ends",
      data: [
        { position: [request.origin.lon, request.origin.lat], fill: WHITE },
        { position: [request.destination.lon, request.destination.lat], fill: INK },
      ],
      getPosition: (d) => d.position,
      getFillColor: (d) => d.fill,
      getLineColor: INK,
      getRadius: 7,
      radiusUnits: "pixels",
      lineWidthUnits: "pixels",
      getLineWidth: 3,
      stroked: true,
    }),
    new TextLayer<{ routeId: RouteId; position: [number, number] }>({
      id: "route-labels",
      data: labels,
      getPosition: (d) => d.position,
      getText: (d) => d.routeId,
      getSize: 13,
      fontWeight: 700,
      fontFamily: '"Inter Variable", Inter, system-ui, sans-serif',
      getColor: (d) => (isSelected(d.routeId) ? WHITE : INK),
      background: true,
      getBackgroundColor: (d) => (isSelected(d.routeId) ? [31, 78, 121] : WHITE),
      backgroundPadding: [7, 4],
      backgroundBorderRadius: 10,
      getBorderColor: INK,
      getBorderWidth: 1,
      pickable: true,
      onClick: select,
      updateTriggers: { getColor: selectedId, getBackgroundColor: selectedId },
    }),
  ];
}

/** `[[west, south], [east, north]]` around every route. */
export function planBounds(plan: PlanResponse): [[number, number], [number, number]] {
  let [west, south, east, north] = [180, 90, -180, -90];
  for (const route of plan.routes) {
    for (const [lon, lat] of route.path as [number, number][]) {
      west = Math.min(west, lon);
      east = Math.max(east, lon);
      south = Math.min(south, lat);
      north = Math.max(north, lat);
    }
  }
  return [
    [west, south],
    [east, north],
  ];
}
