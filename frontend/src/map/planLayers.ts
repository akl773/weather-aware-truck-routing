import type { Layer, PickingInfo } from "@deck.gl/core";
import { PathLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";

import type { PlanRequest, PlanResponse } from "../api/client";
import type { components } from "../api/schema";
import { labelPoints } from "../plan/labels";
import { type LngLat, type Segment, pointAtMile, routeSegments } from "../plan/segments";
import { levelColor } from "../risk/levels";

type RouteId = components["schemas"]["IdEnum"];
type Checkpoint = components["schemas"]["Checkpoint"];

export interface CheckpointPick {
  routeId: RouteId;
  index: number;
  checkpoint: Checkpoint;
}

interface LabelDatum {
  routeId: RouteId;
  position: LngLat;
}

/** The plan's drawable pieces, built once per plan and selection so map updates reuse them. */
export interface PlanGeometry {
  segments: Segment[];
  /** The selected route's checkpoints, drawn larger than the rest. */
  checkpoints: CheckpointPick[];
  otherCheckpoints: CheckpointPick[];
  labels: LabelDatum[];
}

/** The selected route's pieces last, so it draws over the others. */
function selectedLast<T extends { routeId: RouteId }>(items: T[], selectedId: RouteId): T[] {
  return [...items].sort((a, b) => Number(a.routeId === selectedId) - Number(b.routeId === selectedId));
}

function picks(routes: PlanResponse["routes"]): CheckpointPick[] {
  return routes.flatMap((route) =>
    route.checkpoints.map((checkpoint, index) => ({ routeId: route.id, index, checkpoint })),
  );
}

export function planGeometry(plan: PlanResponse, selectedId: RouteId): PlanGeometry {
  const labelAt = labelPoints(plan.routes);
  return {
    segments: selectedLast(plan.routes.flatMap(routeSegments), selectedId),
    checkpoints: picks(plan.routes.filter((route) => route.id === selectedId)),
    otherCheckpoints: picks(plan.routes.filter((route) => route.id !== selectedId)),
    labels: selectedLast(
      plan.routes.map((route) => ({
        routeId: route.id,
        position: labelAt.get(route.id) ?? pointAtMile(route, route.summary.distance_mi / 2),
      })),
      selectedId,
    ),
  };
}

interface PlanLayerProps {
  geometry: PlanGeometry;
  request: PlanRequest;
  selectedId: RouteId;
  highlighted: CheckpointPick | null;
  onSelectRoute: (id: RouteId) => void;
}

const WHITE: [number, number, number] = [255, 255, 255];
const INK: [number, number, number] = [31, 41, 55];
// Routes not selected stay visible for comparison but recede (ui D6).
const DIMMED_ALPHA = 120;

export function planLayers({
  geometry: { segments, checkpoints, otherCheckpoints, labels },
  request,
  selectedId,
  highlighted,
  onSelectRoute,
}: PlanLayerProps): Layer[] {
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
    // Sized on the ground, so a 10-mile interval on a long route does not bead into a chain that
    // hides the line's colours when zoomed out (ui D6).
    new ScatterplotLayer<CheckpointPick>({
      id: "checkpoints-other",
      data: otherCheckpoints,
      getPosition: (c) => [c.checkpoint.lon, c.checkpoint.lat],
      getFillColor: (c) => [...levelColor(c.checkpoint.level), 150],
      getLineColor: [255, 255, 255, 150],
      getRadius: 1200,
      radiusUnits: "meters",
      radiusMinPixels: 1.5,
      radiusMaxPixels: 4,
      lineWidthUnits: "pixels",
      getLineWidth: 1,
      stroked: true,
      pickable: true,
      onClick: select,
    }),
    new ScatterplotLayer<CheckpointPick>({
      id: "checkpoints",
      data: checkpoints,
      getPosition: (c) => [c.checkpoint.lon, c.checkpoint.lat],
      getFillColor: (c) => levelColor(c.checkpoint.level),
      getLineColor: WHITE,
      getRadius: 2000,
      radiusUnits: "meters",
      radiusMinPixels: 3,
      radiusMaxPixels: 6,
      lineWidthUnits: "pixels",
      getLineWidth: 1,
      stroked: true,
      pickable: true,
      onClick: select,
    }),
    // Its own layer, so hovering changes one point's data instead of every checkpoint's radius.
    new ScatterplotLayer<CheckpointPick>({
      id: "checkpoint-highlight",
      data: highlighted ? [highlighted] : [],
      getPosition: (c) => [c.checkpoint.lon, c.checkpoint.lat],
      getFillColor: (c) => [...levelColor(c.checkpoint.level), 255],
      getLineColor: INK,
      getRadius: 8,
      radiusUnits: "pixels",
      lineWidthUnits: "pixels",
      getLineWidth: 2,
      stroked: true,
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
    new TextLayer<LabelDatum>({
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
