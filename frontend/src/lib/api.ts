import type { Feature, Geometry, Point } from "geojson";

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

export type MapLayerFeature = Feature<
  Geometry,
  {
    name: string | null;
    population?: number | null;
    population_density?: number | null;
    item_type?: string;
    source_record_id?: string;
    area_id?: number;
    rank?: number;
    final_score?: number;
    label?: string;
    normalized_factors?: Record<string, number | null>;
    raw_factors?: Record<string, number | null>;
    representative_method?: "point_on_surface";
    longitude?: number;
    latitude?: number;
  }
> & { id: number };

export type AreaRanking = {
  area_id: number;
  area_name: string;
  rank: number;
  final_score: number;
  label: string;
  longitude: number;
  latitude: number;
  normalized_factors: Record<string, number | null>;
  raw_factors: Record<string, number | null>;
  representative_method: "point_on_surface";
};

export type AreaRankingResponse = {
  business_category: BusinessCategory;
  radius_m: number;
  scoring_version: string;
  dataset_fingerprint: string;
  items: AreaRanking[];
};

export type Analysis = {
  latitude: number;
  longitude: number;
  business_category: BusinessCategory;
  radius_m: number;
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
  score: {
    status: string;
    final_score: number | null;
    label: string | null;
    normalized_factors: Record<string, number | null>;
    raw_factors: Record<string, number | null>;
    weights: Record<string, number>;
    missing_factors: string[];
    scoring_version: string;
  };
  dataset_fingerprint: string;
  limitations: string[];
};

export type SearchResult = {
  id: string;
  name: string;
  result_type: "coordinate" | "area" | "business" | "landmark";
  subtitle: string;
  longitude: number;
  latitude: number;
  source_record_id: string | null;
};

export type Analytics = {
  business_category: BusinessCategory;
  radius_m: number;
  scoring_version: string;
  dataset_fingerprint: string;
  category_counts: Array<{ category: BusinessCategory; count: number }>;
  top_opportunities: Array<{
    area_id: number;
    area_name: string;
    final_score: number;
    label: string;
  }>;
  score_distribution: Array<{
    label: string;
    minimum: number;
    maximum: number;
    area_count: number;
  }>;
  population_competition: Array<{
    area_name: string;
    population_density: number;
    competitor_count: number;
    final_score: number;
  }>;
  coverage: Array<{
    key: string;
    label: string;
    value: number;
    unit: string;
    definition: string;
  }>;
};

export type Methodology = {
  coverage: string;
  scoring_version: string;
  dataset_fingerprint: string;
  supported_radii_m: number[];
  representative_area_method: string;
  normalization: string;
  factor_definitions: Record<string, string>;
  categories: Array<{
    category: BusinessCategory;
    weights: Record<string, number>;
  }>;
  datasets: Array<{
    slug: string;
    provider: string;
    source_url: string;
    license_name: string;
    attribution: string;
    observed_at: string | null;
    retrieved_at: string;
  }>;
  limitations: string[];
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
    "/business-categories",
  );
}

export async function fetchBusinesses(category: BusinessCategory) {
  const payload = await request<{ features: BusinessFeature[] }>(
    `/businesses?category=${category}&limit=3000`,
  );
  return payload.features;
}

export async function fetchPopulationLayer() {
  const payload = await request<{ features: MapLayerFeature[] }>(
    "/layers/population",
  );
  return payload.features;
}

export async function fetchPointLayer(
  layer: "transport" | "commercial" | "office" | "education" | "healthcare",
) {
  const payload = await request<{ features: MapLayerFeature[] }>(
    `/layers/points?layer=${layer}&limit=10000`,
  );
  return payload.features;
}

export async function fetchRoadLayer() {
  const payload = await request<{ features: MapLayerFeature[] }>(
    "/layers/roads?limit=10000",
  );
  return payload.features;
}

export function searchLocations(query: string) {
  return request<SearchResult[]>(`/search?q=${encodeURIComponent(query)}&limit=8`);
}

export function fetchAnalytics(category: BusinessCategory, radius: number) {
  return request<Analytics>(
    `/analytics?business_category=${category}&radius_m=${radius}`,
  );
}

export function fetchMethodology() {
  return request<Methodology>("/methodology");
}

export async function fetchOpportunityMap(
  category: BusinessCategory,
  radius: number,
) {
  const payload = await request<{ features: MapLayerFeature[] }>(
    `/opportunity-map?business_category=${category}&radius_m=${radius}`,
  );
  return payload.features;
}

export function fetchAreaRankings(
  category: BusinessCategory,
  radius: number,
  limit = 10,
) {
  return request<AreaRankingResponse>(
    `/area-rankings?business_category=${category}&radius_m=${radius}&limit=${limit}`,
  );
}

export function analyzeLocation(input: {
  latitude: number;
  longitude: number;
  category: BusinessCategory;
  radius: number;
}) {
  return request<Analysis>("/analyze-location", {
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
