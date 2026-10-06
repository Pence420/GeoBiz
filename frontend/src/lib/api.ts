import type { Feature, Geometry, Point } from "geojson";

export type BusinessCategory = "fnb" | "retail" | "services";

export type MapConfig = {
  release_id: number;
  release_key: string;
  taxonomy_version: string;
  tile_url: string | null;
  tile_sha256: string | null;
  bounds: [number, number, number, number];
  min_zoom: number;
  max_zoom: number;
  attribution: string;
  mode: "offline" | "online_fallback";
  fallback_available: boolean;
};

export type Demographics = {
  release_id: number;
  release_key: string;
  dataset_fingerprint: string;
  source_name: string;
  source_url: string;
  observed_at: string | null;
  total_areas: number;
  covered_areas: number;
  total_population: number;
  male: number;
  female: number;
  age_gender: Array<{ age: string; male: number; female: number; total: number }>;
  areas: Array<{
    id: number;
    name: string;
    wilayah: string;
    kecamatan: string;
    population: number;
    population_density: number | null;
    male: number;
    female: number;
  }>;
};

export type BusinessFeature = Feature<
  Point,
  {
    name: string | null;
    category: BusinessCategory;
    source_type: string;
    source_record_id: string;
    business_subtype: string;
    taxonomy_version: string;
    address: string | null;
    brand: string | null;
    operator: string | null;
    opening_hours: string | null;
    phone: string | null;
    website: string | null;
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
  containing_area: ContainingArea;
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
  taxonomy_version: string;
  scoring_version: string;
  competitor_subtype_counts: Record<string, number>;
  nearest_competitors: NearbyBusiness[];
  nearest_transport: NearbyTransport | null;
  nearest_major_road: NearbyRoad | null;
  poi_breakdown: Record<"commercial" | "office" | "education" | "healthcare", Record<string, number>>;
  coverage: AnalysisCoverage;
  source_snapshots: DatasetSnapshot[];
  dataset_fingerprint: string;
  limitations: string[];
};

export type ContainingArea = {
  id: number;
  name: string;
  official_code: string | null;
  coverage_official_code: string | null;
  population_density: number | null;
  area_type: string | null;
  kecamatan: string | null;
  population: number | null;
  population_observed_at: string | null;
};

export type NearbyBusiness = {
  name: string | null;
  business_subtype: string;
  distance_m: number;
  latitude: number;
  longitude: number;
  source_type: string;
  source_record_id: string;
  address: string | null;
  brand: string | null;
  operator: string | null;
  opening_hours: string | null;
  phone: string | null;
  website: string | null;
};

export type NearbyTransport = {
  name: string;
  transport_type: string;
  distance_m: number;
  latitude: number;
  longitude: number;
  source_record_id: string;
};

export type NearbyRoad = {
  name: string | null;
  road_type: string;
  distance_m: number;
  source_type: string;
  source_record_id: string;
};

export type AnalysisCoverage = {
  total_businesses: number;
  named_business_percent: number;
  missing_source_fields: Record<string, number>;
};

export type DatasetSnapshot = {
  slug: string;
  provider: string;
  source_url: string;
  license_name: string;
  attribution: string;
  observed_at: string | null;
  retrieved_at: string;
  sha256: string;
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
  release_key: string;
  taxonomy_version: string;
  category_counts: Array<{ category: BusinessCategory; count: number }>;
  subtype_counts: Array<{ subtype: string; count: number }>;
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
  release_key: string;
  taxonomy_version: string;
  tile_sha256: string | null;
  supported_radii_m: number[];
  representative_area_method: string;
  normalization: string;
  factor_definitions: Record<string, string>;
  categories: Array<{
    category: BusinessCategory;
    weights: Record<string, number>;
  }>;
  taxonomy_rules: Array<{
    category: BusinessCategory;
    subtype: string;
    required_tags: Record<string, string>;
  }>;
  datasets: Array<{
    slug: string;
    provider: string;
    source_url: string;
    license_name: string;
    attribution: string;
    observed_at: string | null;
    retrieved_at: string;
    sha256: string;
  }>;
  limitations: string[];
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

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

export function fetchMapConfig() {
  return request<MapConfig>("/map-config");
}

export function fetchDemographics() {
  return request<Demographics>("/demographics");
}

export async function fetchBusinesses(category: BusinessCategory) {
  const payload = await request<{ features: BusinessFeature[] }>(
    `/businesses?category=${category}&limit=3000`,
  );
  return payload.features;
}

export async function fetchPopulationLayer(expectedReleaseId?: number) {
  const payload = await request<{ features: MapLayerFeature[] }>(
    `/layers/population${expectedReleaseId === undefined ? "" : `?expected_release_id=${expectedReleaseId}`}`,
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
