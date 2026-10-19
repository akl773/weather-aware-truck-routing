import type { Layer } from "@deck.gl/core";
import { IconLayer, SolidPolygonLayer } from "@deck.gl/layers";

import type { CorridorResponse, PlanResponse } from "../api/client";
import type { components } from "../api/schema";
import { FIRST_LABEL_LAYER_ID } from "../map/basemap";
import { type LngLat, pointAtMile } from "../plan/segments";
import type { HeatmapView } from "./colors";
import { truckMile } from "./truck";

type RouteId = components["schemas"]["IdEnum"];

/** Each cell as a square one cell size wide around its centre, built once per corridor. */
export function cellPolygons(corridor: CorridorResponse): LngLat[][] {
  const half = corridor.cell_deg / 2;
  return corridor.cells.map(([lon = 0, lat = 0]) => [
    [lon - half, lat - half],
    [lon + half, lat - half],
    [lon + half, lat + half],
    [lon - half, lat + half],
  ]);
}

interface HeatmapLayerProps {
  polygons: LngLat[][];
  /** RGBA bytes per cell at the slider's hour, a new array each time the hour changes. */
  colors: Uint8ClampedArray;
  hour: number;
  view: HeatmapView;
}

export function heatmapLayer({ polygons, colors, hour, view }: HeatmapLayerProps): Layer {
  return new SolidPolygonLayer<LngLat[], { beforeId: string }>({
    id: "corridor",
    data: polygons,
    getPolygon: (polygon) => polygon,
    getFillColor: (_, { index }) => colors.subarray(index * 4, index * 4 + 4),
    // Only the colour attribute changes with the hour; the geometry is never rebuilt (corridor-heatmap D7).
    updateTriggers: { getFillColor: [hour, view] },
    beforeId: FIRST_LABEL_LAYER_ID,
  });
}

// Material's local_shipping glyph on a disc, as an inline image so the map needs no sprite.
const TRUCK_PATH =
  "M20 8h-3V4H3c-1.1 0-2 .9-2 2v11h2c0 1.66 1.34 3 3 3s3-1.34 3-3h6c0 1.66 1.34 3 3 3s3-1.34 3-3h2v-5zM6 18.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5m13.5-9 1.96 2.5H17V9.5zM18 18.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5";

function truckIcon(disc: string, glyph: string, ring: string) {
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 48 48">` +
    `<circle cx="24" cy="24" r="21" fill="${disc}" stroke="${ring}" stroke-width="3"/>` +
    `<path d="${TRUCK_PATH}" fill="${glyph}" transform="translate(11 11) scale(1.08)"/></svg>`;
  return {
    url: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`,
    width: 64,
    height: 64,
  };
}

const SELECTED_TRUCK = truckIcon("#1f4e79", "#ffffff", "#ffffff");
const OTHER_TRUCK = truckIcon("#ffffff", "#1f2937", "#1f2937");

interface Truck {
  routeId: RouteId;
  position: LngLat;
}

/** Each route's truck where its ETAs put it at `at` (ms), the selected one on top (corridor-heatmap D7). */
export function truckLayer(plan: PlanResponse, selectedId: RouteId, at: number): Layer {
  const trucks: Truck[] = plan.routes
    .map((route) => ({ routeId: route.id, position: pointAtMile(route, truckMile(route, at)) }))
    .sort((a, b) => Number(a.routeId === selectedId) - Number(b.routeId === selectedId));
  return new IconLayer<Truck>({
    id: "trucks",
    data: trucks,
    getPosition: (truck) => truck.position,
    getIcon: (truck) => (truck.routeId === selectedId ? SELECTED_TRUCK : OTHER_TRUCK),
    getSize: (truck) => (truck.routeId === selectedId ? 34 : 24),
    sizeUnits: "pixels",
    updateTriggers: { getIcon: selectedId, getSize: selectedId },
  });
}
