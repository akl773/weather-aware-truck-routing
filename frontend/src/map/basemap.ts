// OpenFreeMap Positron: no API key, and near-greyscale so risk colours stand out (stack D10).
export const BASEMAP_STYLE_URL = "https://tiles.openfreemap.org/styles/positron";

// Contiguous United States, where the routing and weather providers have full coverage.
export const INITIAL_VIEW_STATE = {
  longitude: -96.5,
  latitude: 38.5,
  zoom: 3.8,
};

// The style's first label layer: the heatmap draws beneath it so towns and roads stay readable
// (stack D9, corridor-heatmap D5).
export const FIRST_LABEL_LAYER_ID = "waterway_line_label";
