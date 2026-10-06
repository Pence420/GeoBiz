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
      { id: "background", type: "background", paint: { "background-color": "#f1f3eb" } },
      { id: "water", type: "fill", source: "geobiz", "source-layer": "water", paint: { "fill-color": "#b8d8d4" } },
      { id: "landuse", type: "fill", source: "geobiz", "source-layer": "landuse", minzoom: 7, paint: { "fill-color": ["match", ["get", "class"], "park", "#bad6b3", "#e2ebdb"], "fill-opacity": 0.8 } },
      { id: "buildings", type: "fill", source: "geobiz", "source-layer": "building", minzoom: 13, paint: { "fill-color": "#d9dfd2", "fill-outline-color": "#cad3c3" } },
      { id: "minor-roads", type: "line", source: "geobiz", "source-layer": "transportation", minzoom: 10, paint: { "line-color": "#ffffff", "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.6, 15, 3] } },
      { id: "major-road-casing", type: "line", source: "geobiz", "source-layer": "transportation", filter: ["match", ["get", "class"], ["motorway", "trunk", "primary", "secondary"], true, false], paint: { "line-color": "#c6cfc1", "line-width": ["interpolate", ["linear"], ["zoom"], 7, 2, 15, 9] } },
      { id: "major-roads", type: "line", source: "geobiz", "source-layer": "transportation", filter: ["match", ["get", "class"], ["motorway", "trunk", "primary", "secondary"], true, false], paint: { "line-color": "#fbfcfd", "line-width": ["interpolate", ["linear"], ["zoom"], 7, 1, 15, 7] } },
      { id: "boundaries", type: "line", source: "geobiz", "source-layer": "boundary", paint: { "line-color": "#8da883", "line-width": 1, "line-dasharray": [3, 2] } },
      { id: "waterways", type: "line", source: "geobiz", "source-layer": "waterway", minzoom: 8, paint: { "line-color": "#9bcfd3", "line-width": 1.3 } },
    ],
  };
}
