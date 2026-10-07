import { useEffect, useRef, useState } from "react";
import type { FeatureCollection } from "geojson";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, MapMouseEvent } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { Protocol } from "pmtiles";
import "maplibre-gl/dist/maplibre-gl.css";

import type {
  BusinessCategory,
  BusinessFeature,
  MapConfig,
  MapLayerFeature,
} from "../lib/api";
import { localStyle } from "../map/localStyle";

maplibregl.setWorkerUrl(workerUrl);
const pmtilesProtocol = new Protocol();
maplibregl.addProtocol("pmtiles", pmtilesProtocol.tile);

type Props = {
  mapConfig: MapConfig;
  businesses: BusinessFeature[];
  focusedBusiness: BusinessFeature | null;
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
  fnb: "#335c39",
  retail: "#263c29",
  services: "#6d9f62",
};

export function GeoMap({
  mapConfig,
  businesses,
  focusedBusiness,
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
  const [onlineFallback, setOnlineFallback] = useState(
    mapConfig.mode === "online_fallback",
  );

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    setMapError(null);
    setMapLoaded(false);
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: onlineFallback
        ? "https://tiles.openfreemap.org/styles/liberty"
        : localStyle(mapConfig),
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
      handleMapClick(map, event, onSelectLocation),
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
            "#6098a9",
            0.65,
            "#6d9f62",
            1,
            "#c57f62",
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
              "#edf1e9",
              20,
              "#dce8d4",
              40,
              "#b4d19f",
              60,
              "#7caa6d",
              80,
              "#345f3d",
            ],
            "fill-opacity": 0.36,
            "fill-outline-color": "rgba(60,112,72,0.3)",
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
              "#eef4e9",
              10000,
              "#bed9b3",
              25000,
              "#83b177",
              50000,
              "#385e3f",
            ],
            "fill-opacity": 0.38,
            "fill-outline-color": "rgba(60,112,72,0.28)",
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
          "fill-color": "#426e4b",
          "fill-opacity": 0.1,
          "fill-outline-color": "#426e4b",
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
          "circle-stroke-color": "#426e4b",
          "circle-stroke-width": 4,
        },
      });
      updateBusinesses(map, businesses, category);
      for (const layerId of ["business-points", "business-clusters"]) {
        map.on("mouseenter", layerId, () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", layerId, () => {
          map.getCanvas().style.cursor = "";
        });
      }
      setMapLoaded(true);
    });
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [mapConfig, onSelectLocation, onlineFallback, retryNonce]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapLoaded || !map?.isStyleLoaded()) return;
    updateBusinesses(map, businesses, category);
  }, [businesses, category, mapLoaded]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapLoaded || !map || !focusedBusiness) return;
    showBusinessFeaturePopup(map, focusedBusiness);
  }, [focusedBusiness, mapLoaded]);

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
      <span className={`map-mode-badge ${onlineFallback ? "fallback" : "offline"}`}>
        {onlineFallback ? "Online fallback" : "Offline map"}
      </span>
      {mapError ? (
        <div className="map-error" role="alert">
          <span>Peta dasar gagal dimuat: {mapError}</span>
          {mapConfig.fallback_available && !onlineFallback ? (
            <button type="button" onClick={() => { setMapError(null); setOnlineFallback(true); }}>Use online fallback</button>
          ) : null}
          <button type="button" onClick={() => { setMapError(null); setOnlineFallback(mapConfig.mode === "online_fallback"); setRetryNonce((value) => value + 1); }}>Retry map</button>
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

function handleMapClick(
  map: maplibregl.Map,
  event: MapMouseEvent,
  onSelectLocation: (longitude: number, latitude: number) => void,
) {
  const business = map.getLayer("business-points")
    ? map.queryRenderedFeatures(event.point, { layers: ["business-points"] })[0]
    : undefined;
  if (business?.geometry.type === "Point") {
    showBusinessPopup(map, business);
    return;
  }
  const cluster = map.getLayer("business-clusters")
    ? map.queryRenderedFeatures(event.point, { layers: ["business-clusters"] })[0]
    : undefined;
  const clusterId = Number(cluster?.properties?.cluster_id);
  if (cluster?.geometry.type === "Point" && Number.isInteger(clusterId)) {
    const coordinates = cluster.geometry.coordinates.slice() as [number, number];
    const source = map.getSource("businesses") as GeoJSONSource;
    void source.getClusterExpansionZoom(clusterId).then((zoom) => {
      map.easeTo({ center: coordinates, zoom, duration: 400 });
    }).catch(() => {
      map.easeTo({ center: coordinates, zoom: Math.min(map.getZoom() + 2, 14), duration: 400 });
    });
    return;
  }
  selectMapLocation(map, event, onSelectLocation);
}

function showBusinessPopup(map: maplibregl.Map, feature: maplibregl.MapGeoJSONFeature) {
  if (feature.geometry.type !== "Point") return;
  showBusinessDetails(
    map,
    feature.geometry.coordinates.slice() as [number, number],
    String(feature.properties?.name || "Nama belum tersedia"),
    String(feature.properties?.category || "business"),
    String(feature.properties?.source_type || "record"),
    String(feature.properties?.source_record_id || "unknown"),
  );
}

function showBusinessFeaturePopup(map: maplibregl.Map, business: BusinessFeature) {
  showBusinessDetails(
    map,
    business.geometry.coordinates.slice() as [number, number],
    business.properties.name || "Nama belum tersedia",
    business.properties.category,
    business.properties.source_type,
    business.properties.source_record_id,
  );
}

function showBusinessDetails(
  map: maplibregl.Map,
  coordinates: [number, number],
  name: string,
  businessCategory: string,
  sourceType: string,
  sourceRecordId: string,
) {
  const container = document.createElement("div");
  container.className = "business-popup";
  const title = document.createElement("strong");
  title.textContent = name;
  const categoryLabel = document.createElement("span");
  categoryLabel.textContent = businessCategory;
  const source = document.createElement("small");
  source.textContent = `OSM ${sourceType}/${sourceRecordId}`;
  container.append(title, categoryLabel, source);
  new maplibregl.Popup({ offset: 12 }).setLngLat(coordinates).setDOMContent(container).addTo(map);
  map.easeTo({ center: coordinates, zoom: Math.max(map.getZoom(), 14), duration: 400 });
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
