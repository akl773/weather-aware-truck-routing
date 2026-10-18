import "maplibre-gl/dist/maplibre-gl.css";

import type { Layer, PickingInfo } from "@deck.gl/core";
import { setWorkerUrl } from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { useEffect, useRef } from "react";
import { Map as MapLibreMap, type MapRef, NavigationControl } from "react-map-gl/maplibre";

import { BASEMAP_STYLE_URL, INITIAL_VIEW_STATE } from "./basemap";
import { DeckOverlay } from "./DeckOverlay";

// MapLibre 6 cannot locate its worker inside a Vite bundle on its own.
setWorkerUrl(maplibreWorkerUrl);

type Bounds = [[number, number], [number, number]];

interface MapViewProps {
  layers: Layer[];
  /** Fitted once each time it changes, leaving room for the panel. */
  bounds: Bounds | null;
  onHover?: (info: PickingInfo) => void;
  /** The view starts moving, so anything pinned to a screen position is stale. */
  onMoveStart?: () => void;
}

const WIDE = "(min-width: 900px)";

/** Room around the fitted routes for whatever floats over the map. */
function fitPadding() {
  if (window.matchMedia(WIDE).matches) return { top: 48, bottom: 160, left: 456, right: 48 };
  // The panel covers the top 60% on narrow screens. On a short one that leaves too little room,
  // and MapLibre refuses to fit at all, so both edges shrink to leave at least 30% of the height.
  const height = window.innerHeight;
  const top = height * 0.6 + 24;
  const bottom = 140;
  const scale = Math.min(1, (height * 0.7) / (top + bottom));
  return { top: top * scale, bottom: bottom * scale, left: 24, right: 24 };
}

function cursor({ isDragging, isHovering }: { isDragging: boolean; isHovering: boolean }) {
  return isDragging ? "grabbing" : isHovering ? "pointer" : "grab";
}

export function MapView({ layers, bounds, onHover, onMoveStart }: MapViewProps) {
  const map = useRef<MapRef>(null);

  useEffect(() => {
    if (!bounds || !map.current) return;
    map.current.fitBounds(bounds, {
      padding: fitPadding(),
      duration: 900,
      maxZoom: 9,
    });
  }, [bounds]);

  return (
    <MapLibreMap
      ref={map}
      initialViewState={INITIAL_VIEW_STATE}
      mapStyle={BASEMAP_STYLE_URL}
      style={{ position: "absolute", inset: 0 }}
      attributionControl={{ compact: true }}
      onMoveStart={onMoveStart}
    >
      <NavigationControl position="bottom-right" showCompass={false} />
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
