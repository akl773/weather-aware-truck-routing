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
}

const WIDE = "(min-width: 900px)";

export function MapView({ layers, bounds, onHover }: MapViewProps) {
  const map = useRef<MapRef>(null);

  useEffect(() => {
    if (!bounds || !map.current) return;
    const wide = window.matchMedia(WIDE).matches;
    map.current.fitBounds(bounds, {
      padding: wide
        ? { top: 48, bottom: 160, left: 456, right: 48 }
        : { top: window.innerHeight * 0.6 + 24, bottom: 140, left: 24, right: 24 },
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
    >
      <NavigationControl position="bottom-right" showCompass={false} />
      <DeckOverlay
        interleaved
        layers={layers}
        onHover={(info) => {
          // The map owns the canvas in interleaved mode, so it owns the cursor too.
          const canvas = map.current?.getCanvas();
          if (canvas) canvas.style.cursor = info.picked ? "pointer" : "";
          onHover?.(info);
        }}
      />
    </MapLibreMap>
  );
}
