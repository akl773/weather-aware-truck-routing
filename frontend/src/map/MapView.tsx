import "maplibre-gl/dist/maplibre-gl.css";

import { setWorkerUrl } from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { Map as MapLibreMap, NavigationControl } from "react-map-gl/maplibre";

import { BASEMAP_STYLE_URL, INITIAL_VIEW_STATE } from "./basemap";
import { DeckOverlay } from "./DeckOverlay";

// MapLibre 6 cannot locate its worker inside a Vite bundle on its own.
setWorkerUrl(maplibreWorkerUrl);

export function MapView() {
  return (
    <MapLibreMap
      initialViewState={INITIAL_VIEW_STATE}
      mapStyle={BASEMAP_STYLE_URL}
      style={{ position: "absolute", inset: 0 }}
      attributionControl={{ compact: true }}
    >
      <NavigationControl position="bottom-right" showCompass={false} />
      <DeckOverlay interleaved layers={[]} />
    </MapLibreMap>
  );
}
