import "maplibre-gl/dist/maplibre-gl.css";

import type { Layer, PickingInfo } from "@deck.gl/core";
import { setWorkerUrl } from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import useMediaQuery from "@mui/material/useMediaQuery";
import { useEffect, useRef } from "react";
import {
  AttributionControl,
  Map as MapLibreMap,
  type MapRef,
  NavigationControl,
} from "react-map-gl/maplibre";

import { NARROW_PANEL_SHARE } from "../layout/Panel";
import { BASEMAP_STYLE_URL, INITIAL_VIEW_STATE } from "./basemap";
import { DeckOverlay } from "./DeckOverlay";

// MapLibre 6 cannot locate its worker inside a Vite bundle on its own.
setWorkerUrl(maplibreWorkerUrl);

type Bounds = [[number, number], [number, number]];

interface MapViewProps {
  layers: Layer[];
  /** Fitted once each time it changes, leaving room for the panel and the timeline. */
  bounds: Bounds | null;
  /** Pixels the timeline covers above the map's bottom edge; the fit waits until it is known. */
  bottomInset: number | null;
  onHover?: (info: PickingInfo) => void;
  /** The view starts moving, so anything pinned to a screen position is stale. */
  onMoveStart?: () => void;
}

const WIDE = "(min-width: 900px)";

/** Room around the fitted routes for whatever floats over the map. */
function fitPadding(bottomInset: number) {
  const bottom = bottomInset + 24;
  if (window.matchMedia(WIDE).matches) return { top: 48, bottom, left: 456, right: 48 };
  // The panel covers the top half on narrow screens. On a short one that leaves too little room,
  // and MapLibre refuses to fit at all, so both edges shrink to leave at least 30% of the height.
  const height = window.innerHeight;
  const top = height * NARROW_PANEL_SHARE + 24;
  const scale = Math.min(1, (height * 0.7) / (top + bottom));
  return { top: top * scale, bottom: bottom * scale, left: 24, right: 24 };
}

function cursor({ isDragging, isHovering }: { isDragging: boolean; isHovering: boolean }) {
  return isDragging ? "grabbing" : isHovering ? "pointer" : "grab";
}

export function MapView({ layers, bounds, bottomInset, onHover, onMoveStart }: MapViewProps) {
  const map = useRef<MapRef>(null);
  const fitted = useRef<Bounds | null>(null);
  const wide = useMediaQuery(WIDE);

  useEffect(() => {
    if (!bounds || bottomInset === null || fitted.current === bounds || !map.current) return;
    // Once per plan: the timeline's height changing later must not pull the view from the user.
    fitted.current = bounds;
    map.current.fitBounds(bounds, {
      padding: fitPadding(bottomInset),
      duration: 900,
      maxZoom: 9,
    });
  }, [bounds, bottomInset]);

  return (
    <MapLibreMap
      ref={map}
      initialViewState={INITIAL_VIEW_STATE}
      mapStyle={BASEMAP_STYLE_URL}
      style={{ position: "absolute", inset: 0 }}
      attributionControl={false}
      onMoveStart={onMoveStart}
    >
      {/* The timeline spans the bottom of a wide screen, so the credits move to the top. On a
          narrow one the panel has the top and the timeline stops short of the bottom for them. */}
      <AttributionControl
        key={wide ? "wide" : "narrow"}
        position={wide ? "top-right" : "bottom-right"}
        compact
      />
      {/* Touch screens zoom with a pinch, and the buttons would sit under the timeline. */}
      {wide ? <NavigationControl position="bottom-right" showCompass={false} /> : null}
      <DeckOverlay
        interleaved
        layers={layers}
        // deck.gl sets the shared canvas's cursor every frame, so the pointer is decided here.
        getCursor={cursor}
        // Checkpoints are a few pixels wide when zoomed out; this makes them easy to hover.
        pickingRadius={5}
        onHover={onHover}
      />
    </MapLibreMap>
  );
}
