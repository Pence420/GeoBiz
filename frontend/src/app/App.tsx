import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";

import {
  analyzeLocation,
  fetchBusinesses,
  fetchCategories,
  fetchPointLayer,
  fetchPopulationLayer,
  type Analysis,
  type BusinessCategory,
  type BusinessFeature,
  type MapLayerFeature,
} from "../lib/api";

const GeoMap = lazy(() =>
  import("../components/GeoMap").then((module) => ({ default: module.GeoMap })),
);

const DEFAULT_LOCATION = { latitude: -6.1754, longitude: 106.8272 };
const RADII = [500, 1000, 2000, 3000, 5000];
type LayerKey = "competitors" | "heatmap" | "population" | "transport" | "commercial";

const layerLabels: Record<LayerKey, string> = {
  competitors: "Competitors",
  heatmap: "Heatmap",
  population: "Population",
  transport: "Transit",
  commercial: "Commercial",
};

const categoryLabels: Record<BusinessCategory, string> = {
  restaurant: "Restaurant",
  gym: "Gym",
  pharmacy: "Pharmacy",
};

const metricLabels: Array<[keyof Analysis["nearby_metrics"], string]> = [
  ["competitor_count", "Kompetitor"],
  ["transport_stop_count", "Halte transit"],
  ["commercial_poi_count", "Titik komersial"],
  ["office_count", "Perkantoran"],
  ["university_count", "Kampus & sekolah"],
  ["healthcare_count", "Fasilitas kesehatan"],
];

const factorLabels: Record<string, string> = {
  population_density: "Population",
  competition: "Competition",
  public_transport: "Public transport",
  commercial_activity: "Commercial activity",
  office_activity: "Office density",
  road_accessibility: "Road accessibility",
  healthcare_proximity: "Healthcare proximity",
};

export function App() {
  const [category, setCategory] = useState<BusinessCategory>("restaurant");
  const [radius, setRadius] = useState(1000);
  const [location, setLocation] = useState(DEFAULT_LOCATION);
  const [categories, setCategories] = useState<
    Array<{ slug: BusinessCategory; business_count: number }>
  >([]);
  const [businesses, setBusinesses] = useState<BusinessFeature[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [populationAreas, setPopulationAreas] = useState<MapLayerFeature[]>([]);
  const [transportPoints, setTransportPoints] = useState<MapLayerFeature[]>([]);
  const [commercialPoints, setCommercialPoints] = useState<MapLayerFeature[]>([]);
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({
    competitors: true,
    heatmap: false,
    population: false,
    transport: false,
    commercial: false,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCategories()
      .then(setCategories)
      .catch(() => setError("Data kategori belum bisa dimuat."));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetchBusinesses(category),
      analyzeLocation({ ...location, category, radius }),
    ])
      .then(([features, result]) => {
        setBusinesses(features);
        setAnalysis(result);
      })
      .catch((requestError: Error) => {
        setAnalysis(null);
        setError(requestError.message || "Analisis lokasi gagal dimuat.");
      })
      .finally(() => setLoading(false));
  }, [category, radius, location]);

  useEffect(() => {
    if (layers.population && populationAreas.length === 0) {
      fetchPopulationLayer().then(setPopulationAreas).catch(() =>
        setError("Layer populasi belum bisa dimuat."),
      );
    }
  }, [layers.population, populationAreas.length]);

  useEffect(() => {
    if (layers.transport && transportPoints.length === 0) {
      fetchPointLayer("transport").then(setTransportPoints).catch(() =>
        setError("Layer transit belum bisa dimuat."),
      );
    }
  }, [layers.transport, transportPoints.length]);

  useEffect(() => {
    if (layers.commercial && commercialPoints.length === 0) {
      fetchPointLayer("commercial").then(setCommercialPoints).catch(() =>
        setError("Layer komersial belum bisa dimuat."),
      );
    }
  }, [commercialPoints.length, layers.commercial]);

  const categoryCount = useMemo(
    () =>
      categories.find((item) => item.slug === category)?.business_count ??
      businesses.length,
    [businesses.length, categories, category],
  );

  const selectLocation = useCallback((longitude: number, latitude: number) => {
    setLocation({ longitude, latitude });
  }, []);

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="GeoBiz home">
          <span className="brand-mark" aria-hidden="true">G</span>
          <span>GeoBiz</span>
        </a>
        <nav aria-label="Navigasi utama">
          <a className="nav-link active" href="#overview">Overview</a>
          <a className="nav-link" href="#locations">Locations</a>
          <a className="nav-link" href="#methodology">Methodology</a>
        </nav>
        <div className="project-meta">
          <span className="status-dot" aria-hidden="true" />
          <span><strong>DKI Jakarta</strong><small>Data publik terverifikasi</small></span>
        </div>
      </header>

      <main id="top">
        <section className="workspace" id="overview" aria-label="GeoBiz location analysis">
          <div className="map-column">
            <div className="map-toolbar">
              <div className="location-readout">
                <span className="pin-icon" aria-hidden="true">⌖</span>
                <span><small>Lokasi analisis</small><strong>{analysis?.containing_area.name ?? "DKI Jakarta"}</strong></span>
              </div>
              <label className="select-control">
                <span>Bisnis</span>
                <select value={category} onChange={(event) => setCategory(event.target.value as BusinessCategory)}>
                  {Object.entries(categoryLabels).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>
              <label className="select-control radius-control">
                <span>Radius</span>
                <select value={radius} onChange={(event) => setRadius(Number(event.target.value))}>
                  {RADII.map((value) => <option key={value} value={value}>{value / 1000} km</option>)}
                </select>
              </label>
            </div>

            <div className="map-stage">
              <Suspense fallback={<div className="map-canvas map-loading">Memuat peta DKI Jakarta…</div>}>
                <GeoMap
                  businesses={businesses}
                  category={category}
                  selectedLocation={location}
                  radius={radius}
                  onSelectLocation={selectLocation}
                  layers={layers}
                  populationAreas={populationAreas}
                  transportPoints={transportPoints}
                  commercialPoints={commercialPoints}
                />
              </Suspense>
              <div className="layer-panel" aria-label="Map layers">
                <strong>Map layers</strong>
                {(Object.keys(layerLabels) as LayerKey[]).map((layer) => (
                  <label key={layer}>
                    <input
                      type="checkbox"
                      checked={layers[layer]}
                      onChange={() => setLayers((current) => ({
                        ...current,
                        [layer]: !current[layer],
                      }))}
                    />
                    <span>{layerLabels[layer]}</span>
                  </label>
                ))}
              </div>
            </div>
            <p className="map-hint">Klik titik mana pun di dalam DKI Jakarta untuk menghitung ulang.</p>

            <section className="locations-panel" id="locations">
              <div className="section-heading">
                <div><h2>Bisnis nyata di DKI Jakarta</h2><p>Sumber OpenStreetMap, tanpa data buatan.</p></div>
                <span className="count-badge">{categoryCount.toLocaleString("id-ID")} lokasi</span>
              </div>
              <div className="business-table" role="table" aria-label="Daftar bisnis">
                <div className="table-row table-head" role="row">
                  <span>Nama</span><span>Kategori</span><span>Identitas sumber</span>
                </div>
                {businesses.slice(0, 6).map((business) => (
                  <div className="table-row" role="row" key={business.id}>
                    <span><i className={`business-icon ${business.properties.category}`} aria-hidden="true" />{business.properties.name ?? "Nama belum tersedia"}</span>
                    <span>{categoryLabels[business.properties.category]}</span>
                    <span className="source-id">OSM {business.properties.source_type}/{business.properties.source_record_id}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>

          <aside className="insight-column" aria-label="Hasil analisis">
            <section className="score-card">
              <div className="card-title"><h2>Location score</h2><span className="live-chip">Live</span></div>
              {loading ? (
                <div className="score-loading">Menghitung faktor spasial…</div>
              ) : error ? (
                <div className="error-state"><strong>Analisis belum tersedia</strong><p>{error}</p></div>
              ) : analysis ? (
                <>
                  <div className="score-main">
                    <span className="score-number">{analysis.score.final_score?.toFixed(1) ?? "—"}</span>
                    <span className="score-label">{analysis.score.label ?? "Incomplete"}<small>dari 100</small></span>
                  </div>
                  <div className="score-track"><span style={{ width: `${analysis.score.final_score ?? 0}%` }} /></div>
                  <div className="score-context"><span>{categoryLabels[category]}</span><span>{radius / 1000} km radius</span></div>
                </>
              ) : null}
            </section>

            <section className="metric-card">
              <div className="card-title"><h2>Area signals</h2><span>Radius {radius / 1000} km</span></div>
              <div className="metrics-grid">
                {metricLabels.map(([key, label]) => (
                  <div className="metric" key={key}>
                    <strong>{analysis?.nearby_metrics[key]?.toLocaleString("id-ID") ?? "—"}</strong>
                    <span>{label}</span>
                  </div>
                ))}
              </div>
            </section>

            <section className="factor-card">
              <div className="card-title"><h2>Score breakdown</h2><span>Normalized 0–100</span></div>
              <div className="factor-list">
                {Object.entries(analysis?.score.normalized_factors ?? {}).map(([factor, score]) => (
                  <div className="factor-row" key={factor}>
                    <div><span>{factorLabels[factor] ?? factor}</span><small>{Math.round((analysis?.score.weights[factor] ?? 0) * 100)}% weight</small></div>
                    <div className="factor-track"><i style={{ width: `${score ?? 0}%` }} /></div>
                    <strong>{score?.toFixed(0) ?? "—"}</strong>
                  </div>
                ))}
              </div>
            </section>

            <section className="population-card">
              <div><span>Kepadatan penduduk</span><strong>{analysis?.nearby_metrics.population_density?.toLocaleString("id-ID", { maximumFractionDigits: 0 }) ?? "—"}</strong><small>jiwa / km²</small></div>
              <div className="density-meter">
                <span>Skala 0–50.000</span>
                <div><i style={{ width: `${Math.min(100, (analysis?.nearby_metrics.population_density ?? 0) / 500)}%` }} /></div>
              </div>
            </section>

            <section className="method-card" id="methodology">
              <h2>Transparent by design</h2>
              <p>Skor memakai percentile DKI yang terikat ke fingerprint dataset. Data yang hilang tidak pernah diganti nol.</p>
              <div className="fingerprint"><span>Dataset</span><code>{analysis?.dataset_fingerprint.slice(0, 12) ?? "memuat…"}</code></div>
              <p className="limitation">Skor adalah bukti komparatif lokasi, bukan jaminan keberhasilan bisnis.</p>
            </section>
          </aside>
        </section>
      </main>
    </div>
  );
}
