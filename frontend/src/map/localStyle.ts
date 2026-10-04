import type { StyleSpecification } from "maplibre-gl";

import type { MapConfig } from "../lib/api";

export function localStyle(config: MapConfig): StyleSpecification {
  if (!config.tile_url) throw new Error("Offline tile URL is unavailable");
  return {
    version: 8,
    sources: {
      geobiz: {
        type: "vector",
        url: `pmtiles://${config.tile_url}`,
        attribution: config.attribution,
        bounds: config.bounds,
        minzoom: config.min_zoom,
        maxzoom: config.max_zoom,
      },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#eef1f4" } },
      { id: "water", type: "fill", source: "geobiz", "source-layer": "water", paint: { "fill-color": "#b8dfe0" } },
      { id: "landuse", type: "fill", source: "geobiz", "source-layer": "landuse", minzoom: 7, paint: { "fill-color": ["match", ["get", "class"], "park", "#cddfc8", "#e4e7df"], "fill-opacity": 0.72 } },
      { id: "buildings", type: "fill", source: "geobiz", "source-layer": "building", minzoom: 13, paint: { "fill-color": "#d4d4d7", "fill-outline-color": "#c6c7ca" } },
      { id: "minor-roads", type: "line", source: "geobiz", "source-layer": "transportation", minzoom: 10, paint: { "line-color": "#ffffff", "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.6, 15, 3] } },
      { id: "major-road-casing", type: "line", source: "geobiz", "source-layer": "transportation", filter: ["match", ["get", "class"], ["motorway", "trunk", "primary", "secondary"], true, false], paint: { "line-color": "#ccd1d7", "line-width": ["interpolate", ["linear"], ["zoom"], 7, 2, 15, 9] } },
      { id: "major-roads", type: "line", source: "geobiz", "source-layer": "transportation", filter: ["match", ["get", "class"], ["motorway", "trunk", "primary", "secondary"], true, false], paint: { "line-color": "#fbfcfd", "line-width": ["interpolate", ["linear"], ["zoom"], 7, 1, 15, 7] } },
      { id: "boundaries", type: "line", source: "geobiz", "source-layer": "boundary", paint: { "line-color": "#a8adb5", "line-width": 1, "line-dasharray": [3, 2] } },
      { id: "waterways", type: "line", source: "geobiz", "source-layer": "waterway", minzoom: 8, paint: { "line-color": "#9bcfd3", "line-width": 1.3 } },
    ],
  };
}
