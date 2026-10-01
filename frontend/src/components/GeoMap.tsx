import { useEffect, useRef, useState } from "react";
import type { FeatureCollection } from "geojson";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, MapLayerMouseEvent, MapMouseEvent } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";

import type {
  BusinessCategory,
  BusinessFeature,
  MapLayerFeature,
} from "../lib/api";

maplibregl.setWorkerUrl(workerUrl);

type Props = {
  businesses: BusinessFeature[];
  category: BusinessCategory;
  selectedLocation: { longitude: number; latitude: number };
  radius: number;
  onSelectLocation: (longitude: number, latitude: number) => void;
  layers: {
    opportunity: boolean;
    competitors: boolean;
    heatmap: boolean;
    population: boolean;
    transport: boolean;
    commercial: boolean;
    education: boolean;
    office: boolean;
    roads: boolean;
  };
  opportunityAreas: MapLayerFeature[];
  populationAreas: MapLayerFeature[];
  transportPoints: MapLayerFeature[];
  commercialPoints: MapLayerFeature[];
  educationPoints: MapLayerFeature[];
  officePoints: MapLayerFeature[];
  roads: MapLayerFeature[];
};

const categoryColors: Record<BusinessCategory, string> = {
  restaurant: "#3157e8",
  gym: "#111318",
  pharmacy: "#1f9d73",
};

export function GeoMap({
  businesses,
  category,
  selectedLocation,
  radius,
  onSelectLocation,
  layers,
  opportunityAreas,
  populationAreas,
  transportPoints,
  commercialPoints,
  educationPoints,
  officePoints,
  roads,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [retryNonce, setRetryNonce] = useState(0);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    setMapError(null);
    setMapLoaded(false);
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: "https://tiles.openfreemap.org/styles/liberty",
      center: [106.8272, -6.2],
      zoom: 10.7,
      minZoom: 9,
      maxZoom: 18,
      attributionControl: false,
    });
    map.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "bottom-right",
    );
    map.addControl(
      new maplibregl.AttributionControl({ compact: true }),
      "bottom-left",
    );
    map.addControl(new maplibregl.FullscreenControl(), "bottom-right");
    map.on("click", (event: MapMouseEvent) =>
      selectMapLocation(map, event, onSelectLocation),
    );
    map.on("error", (event) => {
      const message = event.error?.message;
      if (message) setMapError(message);
    });
    map.on("load", () => {
      map.addSource("businesses", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
        cluster: true,
        clusterMaxZoom: 13,
        clusterRadius: 42,
      });
      map.addLayer({
        id: "business-clusters",
        type: "circle",
        source: "businesses",
        filter: ["has", "point_count"],
        paint: {
          "circle-color": categoryColors[category],
          "circle-radius": ["step", ["get", "point_count"], 15, 25, 19, 100, 24],
          "circle-stroke-width": 3,
          "circle-stroke-color": "#ffffff",
        },
      });
      map.addLayer({
        id: "business-heatmap",
        type: "heatmap",
        source: "businesses",
        maxzoom: 15,
        paint: {
          "heatmap-weight": 0.8,
          "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 9, 0.6, 14, 1.8],
          "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 9, 14, 14, 28],
          "heatmap-opacity": 0.72,
          "heatmap-color": [
            "interpolate",
            ["linear"],
            ["heatmap-density"],
            0,
            "rgba(49,87,232,0)",
            0.35,
            "#36b8e6",
            0.65,
            "#3157e8",
            1,
            "#e64646",
          ],
        },
        layout: { visibility: layers.heatmap ? "visible" : "none" },
      }, "business-clusters");
      map.addLayer({
        id: "cluster-count",
        type: "symbol",
        source: "businesses",
        filter: ["has", "point_count"],
        layout: {
          "text-field": ["get", "point_count_abbreviated"],
          "text-size": 11,
        },
        paint: { "text-color": "#ffffff" },
      });
      map.addSource("population", emptySource());
      map.addSource("opportunity", emptySource());
      map.addLayer(
        {
          id: "opportunity-fill",
          type: "fill",
          source: "opportunity",
          layout: { visibility: layers.opportunity ? "visible" : "none" },
          paint: {
            "fill-color": [
              "step",
              ["coalesce", ["get", "final_score"], 0],
              "#eceef2",
              20,
              "#dbe5f2",
              40,
              "#9fbaf5",
              60,
              "#4772e8",
              80,
              "#183bb8",
            ],
            "fill-opacity": 0.58,
            "fill-outline-color": "rgba(20,45,120,0.4)",
          },
        },
        "business-heatmap",
      );
      map.addLayer(
        {
          id: "population-fill",
          type: "fill",
          source: "population",
          layout: { visibility: layers.population ? "visible" : "none" },
          paint: {
            "fill-color": [
              "interpolate",
              ["linear"],
              ["coalesce", ["get", "population_density"], 0],
              0,
              "#edf4ff",
              10000,
              "#b9ccff",
              25000,
              "#6f8df1",
              50000,
              "#243fbe",
            ],
            "fill-opacity": 0.58,
            "fill-outline-color": "rgba(49,87,232,0.35)",
          },
        },
        "business-heatmap",
      );
      map.addSource("transport", clusteredSource());
      addPointClusterLayers(map, "transport", "#36b8e6", layers.transport);
      map.addLayer({
        id: "transport-points",
        type: "circle",
        source: "transport",
        layout: { visibility: layers.transport ? "visible" : "none" },
        paint: {
          "circle-color": "#36b8e6",
          "circle-radius": 4,
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#ffffff",
        },
      });
      map.addSource("commercial", clusteredSource());
      addPointClusterLayers(map, "commercial", "#f0a43b", layers.commercial);
      map.addLayer({
        id: "commercial-points",
        type: "circle",
        source: "commercial",
        layout: { visibility: layers.commercial ? "visible" : "none" },
        paint: {
          "circle-color": "#f0a43b",
          "circle-radius": 3.5,
          "circle-stroke-width": 1,
          "circle-stroke-color": "#ffffff",
        },
      });
      map.addSource("education", clusteredSource());
      addPointClusterLayers(map, "education", "#1f9d73", layers.education);
      addPointLayer(map, "education", "#1f9d73", layers.education);
      map.addSource("office", clusteredSource());
      addPointClusterLayers(map, "office", "#7b61d1", layers.office);
      addPointLayer(map, "office", "#7b61d1", layers.office);
      map.addSource("roads", emptySource());
      map.addLayer({
        id: "roads-line",
        type: "line",
        source: "roads",
        layout: { visibility: layers.roads ? "visible" : "none" },
        paint: {
          "line-color": "#d14e45",
          "line-width": ["interpolate", ["linear"], ["zoom"], 9, 1, 16, 4],
          "line-opacity": 0.72,
        },
      });
      map.addLayer({
        id: "business-points",
        type: "circle",
        source: "businesses",
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-color": categoryColors[category],
          "circle-radius": 6,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });
      map.addSource("selection", {
        type: "geojson",
        data: selectionData(selectedLocation, radius),
      });
      map.addLayer({
        id: "analysis-radius",
        type: "fill",
        source: "selection",
        filter: ["==", ["get", "kind"], "radius"],
        paint: {
          "fill-color": "#3157e8",
          "fill-opacity": 0.1,
          "fill-outline-color": "#3157e8",
        },
      });
      map.addLayer({
        id: "analysis-point",
        type: "circle",
        source: "selection",
        filter: ["==", ["geometry-type"], "Point"],
        paint: {
          "circle-color": "#ffffff",
          "circle-radius": 7,
          "circle-stroke-color": "#3157e8",
          "circle-stroke-width": 4,
        },
      });
      updateBusinesses(map, businesses, category);
      map.on("click", "business-points", (event) => showBusinessPopup(map, event));
      map.on("mouseenter", "business-points", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "business-points", () => {
        map.getCanvas().style.cursor = "";
      });
      setMapLoaded(true);
    });
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [onSelectLocation, retryNonce]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapLoaded || !map?.isStyleLoaded()) return;
    updateBusinesses(map, businesses, category);
  }, [businesses, category, mapLoaded]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapLoaded || !map?.isStyleLoaded()) return;
    (map.getSource("selection") as GeoJSONSource | undefined)?.setData(
      selectionData(selectedLocation, radius),
    );
    map.easeTo({
      center: [selectedLocation.longitude, selectedLocation.latitude],
      zoom: Math.max(map.getZoom(), 12.5),
      duration: 550,
    });
  }, [mapLoaded, radius, selectedLocation]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapLoaded || !map?.isStyleLoaded()) return;
    setSourceData(map, "population", populationAreas);
    setSourceData(map, "opportunity", opportunityAreas);
    setSourceData(map, "transport", transportPoints);
    setSourceData(map, "commercial", commercialPoints);
    setSourceData(map, "education", educationPoints);
    setSourceData(map, "office", officePoints);
    setSourceData(map, "roads", roads);
    setVisibility(map, "business-clusters", layers.competitors);
    setVisibility(map, "cluster-count", layers.competitors);
    setVisibility(map, "business-points", layers.competitors);
    setVisibility(map, "business-heatmap", layers.heatmap);
    setVisibility(map, "population-fill", layers.population);
    setVisibility(map, "opportunity-fill", layers.opportunity);
    setVisibility(map, "transport-clusters", layers.transport);
    setVisibility(map, "transport-cluster-count", layers.transport);
    setVisibility(map, "transport-points", layers.transport);
    setVisibility(map, "commercial-clusters", layers.commercial);
    setVisibility(map, "commercial-cluster-count", layers.commercial);
    setVisibility(map, "commercial-points", layers.commercial);
    setVisibility(map, "education-clusters", layers.education);
    setVisibility(map, "education-cluster-count", layers.education);
    setVisibility(map, "education-points", layers.education);
    setVisibility(map, "office-clusters", layers.office);
    setVisibility(map, "office-cluster-count", layers.office);
    setVisibility(map, "office-points", layers.office);
    setVisibility(map, "roads-line", layers.roads);
  }, [
    commercialPoints,
    educationPoints,
    layers,
    mapLoaded,
    officePoints,
    opportunityAreas,
    populationAreas,
    roads,
    transportPoints,
  ]);

  return (
    <div className="map-frame">
      <div
        className="map-canvas"
        ref={containerRef}
        aria-label="Peta interaktif bisnis DKI Jakarta"
      />
      <button
        className="map-reset"
        type="button"
        onClick={() => mapRef.current?.easeTo({ center: [106.8272, -6.2], zoom: 10.7, duration: 650 })}
      >
        Reset Jakarta
      </button>
      {mapError ? (
        <div className="map-error" role="alert">
          <span>Peta dasar gagal dimuat: {mapError}</span>
          <button type="button" onClick={() => setRetryNonce((value) => value + 1)}>Retry map</button>
        </div>
      ) : null}
    </div>
  );
}

function addPointLayer(
  map: maplibregl.Map,
  sourceId: string,
  color: string,
  visible: boolean,
) {
  map.addLayer({
    id: `${sourceId}-points`,
    type: "circle",
    source: sourceId,
    filter: ["!", ["has", "point_count"]],
    layout: { visibility: visible ? "visible" : "none" },
    paint: {
      "circle-color": color,
      "circle-radius": 4,
      "circle-stroke-width": 1.5,
      "circle-stroke-color": "#ffffff",
    },
  });
}

function showBusinessPopup(map: maplibregl.Map, event: MapLayerMouseEvent) {
  event.originalEvent.stopPropagation();
  const feature = event.features?.[0];
  if (!feature || feature.geometry.type !== "Point") return;
  const coordinates = feature.geometry.coordinates.slice() as [number, number];
  const container = document.createElement("div");
  container.className = "business-popup";
  const title = document.createElement("strong");
  title.textContent = String(feature.properties?.name || "Nama belum tersedia");
  const category = document.createElement("span");
  category.textContent = String(feature.properties?.category || "business");
  const source = document.createElement("small");
  source.textContent = `OSM ${String(feature.properties?.source_type || "record")}/${String(feature.properties?.source_record_id || "unknown")}`;
  container.append(title, category, source);
  new maplibregl.Popup({ offset: 12 }).setLngLat(coordinates).setDOMContent(container).addTo(map);
}

function selectMapLocation(
  map: maplibregl.Map,
  event: MapMouseEvent,
  onSelectLocation: (longitude: number, latitude: number) => void,
) {
  const opportunity = map.getLayer("opportunity-fill")
    ? map.queryRenderedFeatures(event.point, { layers: ["opportunity-fill"] })[0]
    : undefined;
  const longitude = Number(opportunity?.properties?.longitude);
  const latitude = Number(opportunity?.properties?.latitude);
  if (Number.isFinite(longitude) && Number.isFinite(latitude)) {
    onSelectLocation(longitude, latitude);
    return;
  }
  onSelectLocation(event.lngLat.lng, event.lngLat.lat);
}

function emptySource(): maplibregl.GeoJSONSourceSpecification {
  return {
    type: "geojson",
    data: { type: "FeatureCollection", features: [] },
  };
}

function clusteredSource(): maplibregl.GeoJSONSourceSpecification {
  return {
    ...emptySource(),
    cluster: true,
    clusterMaxZoom: 13,
    clusterRadius: 55,
  };
}

function addPointClusterLayers(
  map: maplibregl.Map,
  sourceId: string,
  color: string,
  visible: boolean,
) {
  const visibility = visible ? "visible" : "none";
  map.addLayer({
    id: `${sourceId}-clusters`,
    type: "circle",
    source: sourceId,
    filter: ["has", "point_count"],
    layout: { visibility },
    paint: {
      "circle-color": color,
      "circle-radius": ["step", ["get", "point_count"], 11, 20, 15, 100, 19],
      "circle-stroke-width": 2,
      "circle-stroke-color": "#ffffff",
    },
  });
  map.addLayer({
    id: `${sourceId}-cluster-count`,
    type: "symbol",
    source: sourceId,
    filter: ["has", "point_count"],
    layout: {
      visibility,
      "text-field": ["get", "point_count_abbreviated"],
      "text-size": 9,
    },
    paint: { "text-color": "#ffffff" },
  });
}

function setSourceData(
  map: maplibregl.Map,
  sourceId: string,
  features: MapLayerFeature[],
) {
  (map.getSource(sourceId) as GeoJSONSource | undefined)?.setData({
    type: "FeatureCollection",
    features,
  });
}

function setVisibility(map: maplibregl.Map, layerId: string, visible: boolean) {
  if (map.getLayer(layerId)) {
    map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
  }
}

function updateBusinesses(
  map: maplibregl.Map,
  businesses: BusinessFeature[],
  category: BusinessCategory,
) {
  (map.getSource("businesses") as GeoJSONSource | undefined)?.setData({
    type: "FeatureCollection",
    features: businesses,
  });
  if (map.getLayer("business-clusters")) {
    map.setPaintProperty(
      "business-clusters",
      "circle-color",
      categoryColors[category],
    );
    map.setPaintProperty(
      "business-points",
      "circle-color",
      categoryColors[category],
    );
  }
}

function selectionData(
  location: { longitude: number; latitude: number },
  radius: number,
): FeatureCollection {
  const points = 64;
  const coordinates = Array.from({ length: points + 1 }, (_, index) => {
    const angle = (index / points) * Math.PI * 2;
    const latitudeOffset = (radius / 111_320) * Math.sin(angle);
    const longitudeOffset =
      (radius / (111_320 * Math.cos((location.latitude * Math.PI) / 180))) *
      Math.cos(angle);
    return [
      location.longitude + longitudeOffset,
      location.latitude + latitudeOffset,
    ];
  });
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { kind: "radius" },
        geometry: { type: "Polygon", coordinates: [coordinates] },
      },
      {
        type: "Feature",
        properties: { kind: "point" },
        geometry: {
          type: "Point",
          coordinates: [location.longitude, location.latitude],
        },
      },
    ],
  };
}
