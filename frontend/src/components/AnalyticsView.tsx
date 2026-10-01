import { useEffect, useMemo, useState } from "react";

import {
  fetchAnalytics,
  type Analytics,
  type BusinessCategory,
} from "../lib/api";

const categoryLabels: Record<BusinessCategory, string> = {
  restaurant: "Restaurant",
  gym: "Gym",
  pharmacy: "Pharmacy",
};

type Props = {
  category: BusinessCategory;
  radius: number;
  onCategoryChange: (category: BusinessCategory) => void;
  onRadiusChange: (radius: number) => void;
};

export function AnalyticsView({
  category,
  radius,
  onCategoryChange,
  onRadiusChange,
}: Props) {
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    fetchAnalytics(category, radius)
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((requestError: Error) => {
        if (!cancelled) setError(requestError.message);
      });
    return () => {
      cancelled = true;
    };
  }, [category, radius]);

  const averageScore = useMemo(() => {
    if (!data?.population_competition.length) return null;
    return data.population_competition.reduce((total, item) => total + item.final_score, 0)
      / data.population_competition.length;
  }, [data]);

  return (
    <main id="main-content" className="content-view analytics-view" aria-label="Analytics dashboard">
      <header className="view-heading">
        <div>
          <span>DKI market overview</span>
          <h1>Opportunity analytics</h1>
          <p>Aggregate evidence from the same versioned scores used on the map.</p>
        </div>
        <div className="view-filters">
          <label>Business<select value={category} onChange={(event) => onCategoryChange(event.target.value as BusinessCategory)}>{Object.entries(categoryLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
          <label>Radius<select value={radius} onChange={(event) => onRadiusChange(Number(event.target.value))}>{[500, 1000, 2000, 3000, 5000].map((value) => <option value={value} key={value}>{value < 1000 ? `${value} m` : `${value / 1000} km`}</option>)}</select></label>
        </div>
      </header>

      {error ? <div className="view-error" role="alert"><strong>Analytics unavailable</strong><p>{error}</p></div> : null}
      {!data && !error ? <div className="view-loading" role="status">Calculating aggregate DKI metrics…</div> : null}
      {data ? (
        <>
          <section className="analytics-kpis" aria-label="Analytics summary">
            <article><span>Average area score</span><strong>{averageScore?.toFixed(1)}</strong><small>267 representative observations</small></article>
            <article><span>Highest score</span><strong>{data.top_opportunities[0]?.final_score.toFixed(1)}</strong><small>{data.top_opportunities[0]?.area_name}</small></article>
            {data.category_counts.map((item) => <article key={item.category}><span>{categoryLabels[item.category]} records</span><strong>{item.count.toLocaleString("id-ID")}</strong><small>Traceable OpenStreetMap businesses</small></article>)}
          </section>

          <section className="analytics-grid">
            <article className="analytics-panel opportunity-list-panel">
              <div className="analytics-title"><div><h2>Top opportunity areas</h2><p>{categoryLabels[category]} · {radius / 1000} km radius</p></div><span>Score</span></div>
              <ol className="opportunity-list">
                {data.top_opportunities.map((item) => <li key={item.area_id}><b>{item.area_name}</b><span><strong>{item.final_score.toFixed(1)}</strong><small>{item.label}</small></span></li>)}
              </ol>
            </article>

            <article className="analytics-panel distribution-panel">
              <div className="analytics-title"><div><h2>Score distribution</h2><p>Number of kelurahan in each interpretation band.</p></div><span>267 areas</span></div>
              <div className="distribution-chart">
                {data.score_distribution.map((band) => (
                  <div key={band.label}>
                    <span>{band.label}<small>{band.minimum}–{band.maximum}</small></span>
                    <div><i style={{ width: `${(band.area_count / 267) * 100}%` }} /></div>
                    <strong>{band.area_count}</strong>
                  </div>
                ))}
              </div>
            </article>

            <article className="analytics-panel scatter-panel">
              <div className="analytics-title"><div><h2>Population versus competition</h2><p>Each point is one kelurahan representative observation.</p></div><span>Higher score = larger point</span></div>
              <ScatterPlot data={data.population_competition} />
              <div className="scatter-table" role="table" aria-label="Population and competition text equivalent">
                {data.population_competition.slice(0, 8).map((item) => <div role="row" key={item.area_name}><span>{item.area_name}</span><span>{item.population_density.toLocaleString("id-ID", { maximumFractionDigits: 0 })} people/km²</span><span>{item.competitor_count} competitors</span><strong>{item.final_score.toFixed(1)}</strong></div>)}
              </div>
            </article>

            <article className="analytics-panel coverage-panel">
              <div className="analytics-title"><div><h2>Dataset coverage</h2><p>What the current local snapshot can actually support.</p></div><span>Audited</span></div>
              <div className="coverage-list">
                {data.coverage.map((metric) => <div key={metric.key}><strong>{metric.value.toLocaleString("id-ID")}</strong><span>{metric.label}<small>{metric.definition}</small></span><i>{metric.unit}</i></div>)}
              </div>
            </article>
          </section>
          <footer className="view-provenance">Scoring {data.scoring_version} · dataset {data.dataset_fingerprint.slice(0, 16)} · aggregate evidence, not revenue or predicted business success.</footer>
        </>
      ) : null}
    </main>
  );
}

function ScatterPlot({ data }: { data: Analytics["population_competition"] }) {
  const maxPopulation = Math.max(...data.map((item) => item.population_density), 1);
  const maxCompetition = Math.max(...data.map((item) => item.competitor_count), 1);
  return (
    <svg className="scatter-chart" viewBox="0 0 620 260" role="img" aria-label="Scatter plot of population density against competitor count">
      <line x1="50" y1="220" x2="600" y2="220" />
      <line x1="50" y1="20" x2="50" y2="220" />
      <text x="325" y="252">Population density →</text>
      <text x="10" y="125" transform="rotate(-90 10 125)">Competitors →</text>
      {data.map((item) => (
        <circle
          key={item.area_name}
          cx={50 + (item.population_density / maxPopulation) * 535}
          cy={220 - (item.competitor_count / maxCompetition) * 190}
          r={2.5 + item.final_score / 30}
        >
          <title>{item.area_name}: {item.population_density.toFixed(0)} people/km², {item.competitor_count} competitors, score {item.final_score}</title>
        </circle>
      ))}
    </svg>
  );
}
