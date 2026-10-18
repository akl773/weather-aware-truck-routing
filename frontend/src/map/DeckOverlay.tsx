import { MapLibreOverlay, type MapLibreOverlayProps } from "@deck.gl/maplibre";
import { useControl } from "react-map-gl/maplibre";

// deck.gl renders inside MapLibre's own pass, so its layers can sit beneath labels (stack D9).
export function DeckOverlay(props: MapLibreOverlayProps) {
  const overlay = useControl<MapLibreOverlay>(() => new MapLibreOverlay(props));
  overlay.setProps(props);
  return null;
}
