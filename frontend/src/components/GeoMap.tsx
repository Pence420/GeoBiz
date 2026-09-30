import { useEffect, useRef, useState } from "react";
import type { FeatureCollection } from "geojson";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, MapMouseEvent } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";

import type { BusinessCategory, BusinessFeature } from "../lib/api";

maplibregl.setWorkerUrl(workerUrl);

type Props = {
  businesses: BusinessFeature[];
  category: BusinessCategory;
  selectedLocation: { longitude: number; latitude: number };
  radius: number;
  onSelectLocation: (longitude: number, latitude: number) => void;
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
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
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
    map.on("click", (event: MapMouseEvent) =>
      onSelectLocation(event.lngLat.lng, event.lngLat.lat),
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
    });
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [onSelectLocation]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded()) return;
    updateBusinesses(map, businesses, category);
  }, [businesses, category]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded()) return;
    (map.getSource("selection") as GeoJSONSource | undefined)?.setData(
      selectionData(selectedLocation, radius),
    );
  }, [radius, selectedLocation]);

  return (
    <div className="map-frame">
      <div
        className="map-canvas"
        ref={containerRef}
        aria-label="Peta interaktif bisnis DKI Jakarta"
      />
      {mapError ? <p className="map-error">Peta dasar gagal dimuat: {mapError}</p> : null}
    </div>
  );
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
