import type { Feature, Point } from "geojson";

export type BusinessCategory = "restaurant" | "gym" | "pharmacy";

export type BusinessFeature = Feature<
  Point,
  {
    name: string | null;
    category: BusinessCategory;
    source_type: string;
    source_record_id: string;
  }
> & { id: number };

export type Analysis = {
  containing_area: { name: string; population_density: number | null };
  nearby_metrics: {
    competitor_count: number;
    transport_stop_count: number | null;
    commercial_poi_count: number | null;
    office_count: number | null;
    university_count: number | null;
    healthcare_count: number | null;
    population_density: number | null;
    nearest_major_road_m: number | null;
  };
  score: { status: string; final_score: number | null; label: string | null };
  dataset_fingerprint: string;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail?.message ?? `Request gagal (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function fetchCategories() {
  return request<Array<{ slug: BusinessCategory; business_count: number }>>(
    "/categories",
  );
}

export async function fetchBusinesses(category: BusinessCategory) {
  const payload = await request<{ features: BusinessFeature[] }>(
    `/businesses?category=${category}&limit=3000`,
  );
  return payload.features;
}

export function analyzeLocation(input: {
  latitude: number;
  longitude: number;
  category: BusinessCategory;
  radius: number;
}) {
  return request<Analysis>("/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      latitude: input.latitude,
      longitude: input.longitude,
      business_category: input.category,
      radius_m: input.radius,
    }),
  });
}
