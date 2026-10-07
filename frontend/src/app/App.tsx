import {
  Fragment,
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
} from "react";

import { NearbyEvidence } from "../components/NearbyEvidence";
import { DashboardShell, type ViewKey } from "../components/DashboardShell";
import { MapControls, type LayerState } from "../components/MapControls";
import {
  analyzeLocation,
  fetchAreaRankings,
  fetchBusinesses,
  fetchCategories,
  fetchMapConfig,
  fetchOpportunityMap,
  fetchPointLayer,
  fetchPopulationLayer,
  fetchRoadLayer,
  type Analysis,
  type AreaRanking,
  type BusinessCategory,
  type BusinessFeature,
  type MapLayerFeature,
  type MapConfig,
} from "../lib/api";

const GeoMap = lazy(() =>
  import("../components/GeoMap").then((module) => ({ default: module.GeoMap })),
);
const AnalyticsView = lazy(() =>
  import("../components/AnalyticsView").then((module) => ({ default: module.AnalyticsView })),
);
const DemographicsView = lazy(() =>
  import("../components/DemographicsView").then((module) => ({ default: module.DemographicsView })),
);
const MethodologyView = lazy(() =>
  import("../components/MethodologyView").then((module) => ({ default: module.MethodologyView })),
);

const DEFAULT_LOCATION = { latitude: -6.1754, longitude: 106.8272 };
const categoryLabels: Record<BusinessCategory, string> = {
  fnb: "F&B",
  retail: "Retail",
  services: "Services",
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
  const [activeView, setActiveView] = useState<ViewKey>(() => viewFromHash());
  const [category, setCategory] = useState<BusinessCategory>("fnb");
  const [radius, setRadius] = useState(1000);
  const [location, setLocation] = useState(DEFAULT_LOCATION);
  const [categories, setCategories] = useState<
    Array<{ slug: BusinessCategory; business_count: number }>
  >([]);
  const [businesses, setBusinesses] = useState<BusinessFeature[]>([]);
  const [businessLoading, setBusinessLoading] = useState(true);
  const [businessError, setBusinessError] = useState<string | null>(null);
  const [businessRequest, setBusinessRequest] = useState(0);
  const [focusedBusiness, setFocusedBusiness] = useState<BusinessFeature | null>(null);
  const [analysisResult, setAnalysisResult] = useState<{ key: string; value: Analysis } | null>(null);
  const [populationAreas, setPopulationAreas] = useState<MapLayerFeature[]>([]);
  const [opportunityAreas, setOpportunityAreas] = useState<MapLayerFeature[]>([]);
  const [rankings, setRankings] = useState<AreaRanking[]>([]);
  const [comparedAreaIds, setComparedAreaIds] = useState<number[]>([]);
  const [opportunityError, setOpportunityError] = useState<string | null>(null);
  const [transportPoints, setTransportPoints] = useState<MapLayerFeature[]>([]);
  const [commercialPoints, setCommercialPoints] = useState<MapLayerFeature[]>([]);
  const [educationPoints, setEducationPoints] = useState<MapLayerFeature[]>([]);
  const [officePoints, setOfficePoints] = useState<MapLayerFeature[]>([]);
  const [roads, setRoads] = useState<MapLayerFeature[]>([]);
  const [minimumScore, setMinimumScore] = useState(0);
  const [maximumCompetition, setMaximumCompetition] = useState<number | null>(null);
  const [minimumPopulation, setMinimumPopulation] = useState(0);
  const [analysisRequest, setAnalysisRequest] = useState(0);
  const [layers, setLayers] = useState<LayerState>({
    opportunity: true,
    competitors: true,
    heatmap: false,
    population: false,
    transport: false,
    commercial: false,
    education: false,
    office: false,
    roads: false,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mapConfig, setMapConfig] = useState<MapConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const selectionKey = JSON.stringify([
    mapConfig?.release_id,
    category,
    radius,
    location.latitude,
    location.longitude,
  ]);
  const analysis = analysisResult?.key === selectionKey ? analysisResult.value : null;

  useEffect(() => {
    fetchMapConfig().then(setMapConfig).catch((requestError: Error) => {
      setConfigError(requestError.message || "Map configuration is unavailable.");
    });
  }, []);

  useEffect(() => {
    const syncView = () => setActiveView(viewFromHash());
    window.addEventListener("hashchange", syncView);
    return () => window.removeEventListener("hashchange", syncView);
  }, []);

  useEffect(() => {
    if (mapConfig?.taxonomy_version !== "v2.0.0") return;
    fetchCategories()
      .then(setCategories)
      .catch(() => setError("Data kategori belum bisa dimuat."));
  }, [mapConfig?.taxonomy_version]);

  useEffect(() => {
    if (!mapConfig || mapConfig.taxonomy_version !== "v2.0.0") return;
    let cancelled = false;
    setBusinesses([]);
    setBusinessLoading(true);
    setBusinessError(null);
    fetchBusinesses(category, mapConfig.release_id)
      .then((features) => {
        if (!cancelled) setBusinesses(features);
      })
      .catch((requestError: Error) => {
        if (cancelled) return;
        setBusinesses([]);
        setBusinessError(requestError.message || "Data bisnis belum bisa dimuat.");
      })
      .finally(() => {
        if (!cancelled) setBusinessLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [businessRequest, category, mapConfig]);

  useEffect(() => {
    if (mapConfig?.taxonomy_version !== "v2.0.0") return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setAnalysisResult(null);
    analyzeLocation({ ...location, category, radius })
      .then((result) => {
        if (cancelled) return;
        setAnalysisResult({ key: selectionKey, value: result });
      })
      .catch((requestError: Error) => {
        if (cancelled) return;
        setAnalysisResult(null);
        setError(requestError.message || "Analisis lokasi gagal dimuat.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [analysisRequest, category, radius, location, mapConfig?.taxonomy_version, selectionKey]);

  useEffect(() => {
    if (mapConfig?.taxonomy_version !== "v2.0.0") return;
    let cancelled = false;
    setOpportunityError(null);
    setOpportunityAreas([]);
    setRankings([]);
    setComparedAreaIds([]);
    Promise.all([
      fetchOpportunityMap(category, radius),
      fetchAreaRankings(category, radius),
    ])
      .then(([features, response]) => {
        if (cancelled) return;
        setOpportunityAreas(features);
        setRankings(response.items);
      })
      .catch((requestError: Error) => {
        if (cancelled) return;
        setOpportunityAreas([]);
        setRankings([]);
        setOpportunityError(requestError.message || "Ranking area belum tersedia.");
      });
    return () => {
      cancelled = true;
    };
  }, [category, radius, mapConfig?.taxonomy_version]);

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

  useEffect(() => {
    if (layers.education && educationPoints.length === 0) {
      fetchPointLayer("education").then(setEducationPoints).catch(() =>
        setError("Layer pendidikan belum bisa dimuat."),
      );
    }
  }, [educationPoints.length, layers.education]);

  useEffect(() => {
    if (layers.office && officePoints.length === 0) {
      fetchPointLayer("office").then(setOfficePoints).catch(() =>
        setError("Layer perkantoran belum bisa dimuat."),
      );
    }
  }, [layers.office, officePoints.length]);

  useEffect(() => {
    if (layers.roads && roads.length === 0) {
      fetchRoadLayer().then(setRoads).catch(() =>
        setError("Layer jalan belum bisa dimuat."),
      );
    }
  }, [layers.roads, roads.length]);

  const categoryCount = useMemo(
    () =>
      categories.find((item) => item.slug === category)?.business_count ??
      businesses.length,
    [businesses.length, categories, category],
  );

  const selectLocation = useCallback((longitude: number, latitude: number) => {
    setLocation({ longitude, latitude });
  }, []);
  const changeCategory = useCallback((value: BusinessCategory) => {
    setFocusedBusiness(null);
    setCategory(value);
  }, []);

  const comparedAreas = rankings.filter((area) =>
    comparedAreaIds.includes(area.area_id),
  );

  const filteredOpportunityAreas = useMemo(
    () => opportunityAreas.filter((area) => {
      const score = area.properties.final_score ?? 0;
      const competition = area.properties.raw_factors?.competition ?? 0;
      const population = area.properties.raw_factors?.population_density ?? 0;
      return score >= minimumScore
        && (maximumCompetition == null || competition <= maximumCompetition)
        && population >= minimumPopulation;
    }),
    [maximumCompetition, minimumPopulation, minimumScore, opportunityAreas],
  );

  const filteredRankings = useMemo(
    () => rankings.filter((area) => {
      const competition = area.raw_factors.competition ?? 0;
      const population = area.raw_factors.population_density ?? 0;
      return area.final_score >= minimumScore
        && (maximumCompetition == null || competition <= maximumCompetition)
        && population >= minimumPopulation;
    }),
    [maximumCompetition, minimumPopulation, minimumScore, rankings],
  );

  const toggleComparison = (areaId: number) => {
    setComparedAreaIds((current) =>
      current.includes(areaId)
        ? current.filter((id) => id !== areaId)
        : current.length < 3
          ? [...current, areaId]
          : current,
    );
  };

  if (configError) {
    return <div className="compatibility-state" role="alert"><strong>GeoBiz configuration unavailable</strong><p>{configError}</p></div>;
  }
  if (!mapConfig) {
    return <div className="compatibility-state" role="status">Loading active GeoBiz release…</div>;
  }
  if (mapConfig.taxonomy_version !== "v2.0.0") {
    return <div className="compatibility-state" role="alert"><strong>GeoBiz v2 data is required</strong><p>The active release uses taxonomy {mapConfig.taxonomy_version}. Run the on-demand data refresh before opening this interface.</p></div>;
  }

  return (
    <DashboardShell activeView={activeView} releaseKey={mapConfig.release_key}>

      {activeView === "overview" ? <main id="main-content">
        <h1 className="sr-only">GeoBiz DKI Jakarta Business Location Intelligence</h1>
        <section className="workspace" id="overview" aria-label="GeoBiz location analysis">
          <div className="map-column">
            <MapControls
              category={category}
              radius={radius}
              layers={layers}
              minimumScore={minimumScore}
              maximumCompetition={maximumCompetition}
              minimumPopulation={minimumPopulation}
              visibleAreas={filteredOpportunityAreas.length}
              onSelectLocation={selectLocation}
              onCategoryChange={changeCategory}
              onRadiusChange={setRadius}
              onLayersChange={setLayers}
              onMinimumScoreChange={setMinimumScore}
              onMaximumCompetitionChange={setMaximumCompetition}
              onMinimumPopulationChange={setMinimumPopulation}
            />

            <div className="map-stage">
              <Suspense fallback={<div className="map-canvas map-loading">Memuat peta DKI Jakarta…</div>}>
                <GeoMap
                  mapConfig={mapConfig}
                  businesses={businesses}
                  focusedBusiness={focusedBusiness}
                  category={category}
                  selectedLocation={location}
                  radius={radius}
                  onSelectLocation={selectLocation}
                  layers={layers}
                  opportunityAreas={filteredOpportunityAreas}
                  populationAreas={populationAreas}
                  transportPoints={transportPoints}
                  commercialPoints={commercialPoints}
                  educationPoints={educationPoints}
                  officePoints={officePoints}
                  roads={roads}
                />
              </Suspense>
              {layers.opportunity ? (
                <div className="opportunity-legend" aria-label="Opportunity score legend">
                  <strong>Opportunity score</strong>
                  <div><i className="band very-low" /><span>0–20</span></div>
                  <div><i className="band low" /><span>21–40</span></div>
                  <div><i className="band moderate" /><span>41–60</span></div>
                  <div><i className="band good" /><span>61–80</span></div>
                  <div><i className="band high" /><span>81–100</span></div>
                </div>
              ) : null}
            </div>
            {businessLoading ? <p className="business-layer-status" role="status">Memuat seluruh titik bisnis…</p> : null}
            {businessError ? (
              <div className="business-layer-status business-layer-error" role="alert">
                <span><strong>Data bisnis peta belum lengkap</strong> · {businessError}</span>
                <button type="button" onClick={() => setBusinessRequest((value) => value + 1)}>Coba muat bisnis lagi</button>
              </div>
            ) : null}
            <p className="map-hint"><span>Klik titik mana pun di dalam DKI Jakarta untuk menghitung ulang.</span><strong>{analysis?.containing_area.name ?? "DKI Jakarta"} · {location.latitude.toFixed(5)}, {location.longitude.toFixed(5)}</strong></p>

            <section className="locations-panel opportunity-panel" id="locations">
              <div className="section-heading">
                <div><h2>Top opportunity areas</h2><p>Skor titik representatif di dalam kelurahan, bukan nilai seragam seluruh polygon.</p></div>
                <span className="count-badge">{categoryLabels[category]} · {radius / 1000} km</span>
              </div>
              {opportunityError ? (
                <div className="panel-empty"><strong>Ranking belum tersedia</strong><span>{opportunityError}</span></div>
              ) : (
                <div className="ranking-table" role="table" aria-label="Peringkat opportunity kelurahan">
                  <div className="ranking-row ranking-head" role="row">
                    <span role="columnheader">Area</span><span role="columnheader">Score</span><span role="columnheader">Population</span><span role="columnheader">Competition</span><span role="columnheader">Access</span><span role="columnheader">Compare</span>
                  </div>
                  {filteredRankings.slice(0, 8).map((area) => {
                    const selected = comparedAreaIds.includes(area.area_id);
                    const disabled = !selected && comparedAreaIds.length >= 3;
                    return (
                      <div className="ranking-row" role="row" key={area.area_id}>
                        <span role="cell"><button className="area-link" type="button" onClick={() => selectLocation(area.longitude, area.latitude)}>
                          <b>{area.rank}</b><span>{area.area_name}<small>Analyze representative point</small></span>
                        </button></span>
                        <span className="ranking-score" role="cell"><strong>{area.final_score.toFixed(1)}</strong><small>{area.label}</small></span>
                        <span role="cell">{formatFactor(area, "population_density")}</span>
                        <span role="cell">{formatFactor(area, "competition")}</span>
                        <span role="cell">{formatFactor(area, "road_accessibility")}</span>
                        <span role="cell"><label className="compare-control">
                          <input
                            type="checkbox"
                            checked={selected}
                            disabled={disabled}
                            aria-label={`Compare ${area.area_name}`}
                            onChange={() => toggleComparison(area.area_id)}
                          />
                          <span>{selected ? "Pinned" : "Pin"}</span>
                        </label></span>
                      </div>
                    );
                  })}
                </div>
              )}
              {comparedAreas.length > 0 ? (
                <div className="comparison" aria-label="Area comparison">
                  <div className="comparison-title"><strong>Area comparison</strong><span>{comparedAreas.length}/3 pinned</span></div>
                  <div className="comparison-grid" style={{ "--area-count": comparedAreas.length } as CSSProperties}>
                    <span className="comparison-label">Area</span>
                    {comparedAreas.map((area) => <strong key={area.area_id}>{area.area_name}</strong>)}
                    <span className="comparison-label">Final score</span>
                    {comparedAreas.map((area) => <span key={area.area_id}>{area.final_score.toFixed(1)}</span>)}
                    {Object.entries(factorLabels).map(([factor, label]) => (
                      <Fragment key={factor}>
                        <span className="comparison-label">{label}</span>
                        {comparedAreas.map((area) => <span key={area.area_id}>{formatFactor(area, factor)}</span>)}
                      </Fragment>
                    ))}
                  </div>
                </div>
              ) : null}
            </section>

            <section className="locations-panel">
              <div className="section-heading">
                <div><h2>Bisnis nyata di DKI Jakarta</h2><p>Sumber OpenStreetMap, tanpa data buatan.</p></div>
                <span className="count-badge">{businessLoading ? "Memuat titik…" : businessError ? "Titik belum lengkap" : `${businesses.length.toLocaleString("id-ID")} titik peta`} · {categoryCount.toLocaleString("id-ID")} tercatat</span>
              </div>
              <div className="business-table" role="table" aria-label="Daftar bisnis">
                <div className="table-row table-head" role="row">
                  <span role="columnheader">Nama</span><span role="columnheader">Kategori</span><span role="columnheader">Identitas sumber</span>
                </div>
                {businesses.slice(0, 6).map((business) => (
                  <div className="table-row" role="row" key={business.id}>
                    <span role="cell">
                      <i className={`business-icon ${business.properties.category}`} aria-hidden="true" />
                      <button
                        className="business-inspect"
                        type="button"
                        onClick={() => setFocusedBusiness(business)}
                        aria-label={`Inspect ${business.properties.name ?? "unnamed business"} on map`}
                      >
                        {business.properties.name ?? "Nama belum tersedia"}
                      </button>
                    </span>
                    <span role="cell">{categoryLabels[business.properties.category]}</span>
                    <span className="source-id" role="cell">OSM {business.properties.source_type}/{business.properties.source_record_id}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>

          <aside className="insight-column" aria-label="Hasil analisis">
            <section className="score-card">
              <div className="card-title"><h2>Location score</h2><span className="live-chip">Live</span></div>
              {loading ? (
                <div className="score-loading" role="status">Menghitung faktor spasial…</div>
              ) : error ? (
                <div className="error-state" role="alert"><strong>Analisis belum tersedia</strong><p>{error}</p><button type="button" onClick={() => setAnalysisRequest((value) => value + 1)}>Retry analysis</button></div>
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

            <section className="candidate-card" aria-label="Area peluang teratas">
              <div className="card-title"><h2>Top areas</h2><span>{categoryLabels[category]} · {radius / 1000} km</span></div>
              <p>Titik representatif kelurahan dengan skor tertinggi.</p>
              {opportunityError ? <div className="candidate-empty">Ranking belum tersedia.</div> : filteredRankings.length === 0 ? <div className="candidate-empty">Belum ada area sesuai filter.</div> : (
                <div className="candidate-list">
                  {filteredRankings.slice(0, 3).map((area) => (
                    <button type="button" key={area.area_id} onClick={() => selectLocation(area.longitude, area.latitude)}>
                      <span className="candidate-rank">{String(area.rank).padStart(2, "0")}</span>
                      <span className="candidate-name"><strong>{area.area_name}</strong><small>Analisis titik area</small></span>
                      <span className="candidate-score">{area.final_score.toFixed(1)}</span>
                    </button>
                  ))}
                </div>
              )}
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

            {analysis ? <NearbyEvidence analysis={analysis} /> : null}

            <section className="method-card" id="methodology">
              <h2>Transparent by design</h2>
              <p>Skor memakai percentile DKI yang terikat ke fingerprint dataset. Data yang hilang tidak pernah diganti nol.</p>
              <div className="fingerprint"><span>Dataset</span><code>{analysis?.dataset_fingerprint.slice(0, 12) ?? "memuat…"}</code></div>
              <div className="fingerprint"><span>Scoring version</span><code>{analysis?.score.scoring_version ?? "memuat…"}</code></div>
              {analysis?.limitations.map((limitation) => <p className="data-limitation" key={limitation}>{limitation}</p>)}
              <p className="limitation">Skor adalah bukti komparatif lokasi, bukan jaminan keberhasilan bisnis.</p>
            </section>
          </aside>
        </section>
      </main> : null}
      {activeView === "analytics" ? (
        <Suspense fallback={<ViewLoading label="analytics" />}>
          <AnalyticsView
            category={category}
            radius={radius}
            onCategoryChange={changeCategory}
            onRadiusChange={setRadius}
          />
        </Suspense>
      ) : null}
      {activeView === "demographics" ? (
        <Suspense fallback={<ViewLoading label="demographics" />}>
          <DemographicsView releaseId={mapConfig.release_id} />
        </Suspense>
      ) : null}
      {activeView === "methodology" ? (
        <Suspense fallback={<ViewLoading label="methodology" />}>
          <MethodologyView />
        </Suspense>
      ) : null}
    </DashboardShell>
  );
}

function ViewLoading({ label }: { label: string }) {
  return <main className="content-view view-loading" role="status">Loading {label}…</main>;
}

function formatFactor(area: AreaRanking, factor: string) {
  const score = area.normalized_factors[factor];
  return score == null ? "—" : score.toFixed(0);
}

function viewFromHash(): ViewKey {
  if (window.location.hash === "#analytics") return "analytics";
  if (window.location.hash === "#demographics") return "demographics";
  if (window.location.hash === "#methodology-view") return "methodology";
  return "overview";
}
