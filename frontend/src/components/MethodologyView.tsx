import { useEffect, useState } from "react";

import { fetchMethodology, type Methodology } from "../lib/api";

const factorLabels: Record<string, string> = {
  population_density: "Population density",
  competition: "Competition",
  public_transport: "Public transport",
  commercial_activity: "Commercial activity",
  office_activity: "Office activity",
  road_accessibility: "Road accessibility",
  healthcare_proximity: "Healthcare proximity",
};

export function MethodologyView() {
  const [data, setData] = useState<Methodology | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMethodology().then(setData).catch((requestError: Error) => setError(requestError.message));
  }, []);

  return (
    <main id="main-content" className="content-view methodology-view" aria-label="Methodology and data sources">
      <header className="view-heading methodology-heading">
        <div>
          <span>Transparent by design</span>
          <h1>How GeoBiz builds a score</h1>
          <p>Source provenance, factor definitions, normalization, weights, and limitations for academic review.</p>
        </div>
        {data ? <div className="method-stamp"><span>Scoring version</span><strong>{data.scoring_version}</strong><small>{data.coverage}</small></div> : null}
      </header>
      {error ? <div className="view-error" role="alert"><strong>Methodology unavailable</strong><p>{error}</p></div> : null}
      {!data && !error ? <div className="view-loading" role="status">Loading methodology and source snapshots…</div> : null}
      {data ? (
        <>
          <section className="method-intro">
            <article><span>01</span><div><h2>Representative observation</h2><p>{data.representative_area_method}</p></div></article>
            <article><span>02</span><div><h2>Normalization</h2><p>{data.normalization}</p></div></article>
            <article><span>03</span><div><h2>Weighted score</h2><p>Only required factors with approved category weights contribute. Missing required evidence returns an incomplete result and is never replaced with zero.</p></div></article>
          </section>

          <section className="method-grid">
            <article className="method-panel factor-definitions">
              <div className="analytics-title"><div><h2>Factor definitions</h2><p>What each normalized bar means.</p></div><span>0–100</span></div>
              {Object.entries(data.factor_definitions).map(([factor, definition]) => <div key={factor}><strong>{factorLabels[factor] ?? factor}</strong><p>{definition}</p></div>)}
            </article>
            <article className="method-panel weight-panel">
              <div className="analytics-title"><div><h2>Approved category weights</h2><p>Stored in PostgreSQL, not hard-coded UI branches.</p></div><span>Total 100%</span></div>
              <div className="weight-table" role="table" aria-label="Category scoring weights">
                <div role="row"><strong>Factor</strong>{data.categories.map((item) => <strong key={item.category}>{item.category}</strong>)}</div>
                {Object.keys(factorLabels).map((factor) => <div role="row" key={factor}><span>{factorLabels[factor]}</span>{data.categories.map((item) => <span key={item.category}>{Math.round((item.weights[factor] ?? 0) * 100)}%</span>)}</div>)}
              </div>
            </article>
          </section>

          <section className="source-panel">
            <div className="analytics-title"><div><h2>Source snapshots</h2><p>Every promoted dataset is checksum-verified before analysis.</p></div><span>{data.datasets.length} sources</span></div>
            <div className="source-table" role="table" aria-label="Dataset source snapshots">
              <div role="row"><span>Provider / dataset</span><span>Observed</span><span>Retrieved</span><span>License</span></div>
              {data.datasets.map((dataset) => <div role="row" key={dataset.slug}><span><a href={dataset.source_url} target="_blank" rel="noreferrer">{dataset.provider}</a><small>{dataset.slug}<br />{dataset.attribution}</small></span><span>{formatDate(dataset.observed_at)}</span><span>{formatDate(dataset.retrieved_at)}</span><span>{dataset.license_name}</span></div>)}
            </div>
          </section>

          <section className="limitations-panel">
            <div><h2>Interpretation limits</h2><p>These constraints are part of the result, not fine print.</p></div>
            <ul>{data.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
          </section>
          <footer className="view-provenance">Dataset fingerprint {data.dataset_fingerprint} · supported radii {data.supported_radii_m.map((value) => `${value / 1000} km`).join(", ")}.</footer>
        </>
      ) : null}
    </main>
  );
}

function formatDate(value: string | null) {
  if (!value) return "Not published";
  return new Intl.DateTimeFormat("id-ID", { dateStyle: "medium" }).format(new Date(value));
}
