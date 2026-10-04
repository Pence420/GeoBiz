import type { Analysis } from "../lib/api";

export function NearbyEvidence({ analysis }: { analysis: Pick<Analysis,
  "competitor_subtype_counts" | "nearest_competitors" | "nearest_transport" |
  "nearest_major_road" | "coverage" | "containing_area"
> }) {
  const subtypeTotal = Object.values(analysis.competitor_subtype_counts).reduce(
    (total, count) => total + count, 0,
  );
  return (
    <section className="evidence-card" aria-label="Detailed location evidence">
      <div className="card-title"><h2>Nearby evidence</h2><span>Mapped records</span></div>
      <div className="area-evidence">
        <div><span>Kelurahan</span><strong>{analysis.containing_area.name}</strong></div>
        <div><span>Kecamatan</span><strong>{analysis.containing_area.kecamatan ?? "Not mapped"}</strong></div>
        <div><span>Population period</span><strong>{formatPeriod(analysis.containing_area.population_observed_at)}</strong></div>
      </div>
      <div className="subtype-composition">
        <h3>Competitor mix</h3>
        {Object.entries(analysis.competitor_subtype_counts).map(([subtype, count]) => (
          <div key={subtype}><span>{subtype}</span><i><b style={{ width: `${subtypeTotal ? count / subtypeTotal * 100 : 0}%` }} /></i><strong>{count}</strong></div>
        ))}
      </div>
      <div className="nearest-list">
        <h3>Nearest competitors</h3>
        {analysis.nearest_competitors.length ? analysis.nearest_competitors.map((business) => (
          <article key={`${business.source_type}-${business.source_record_id}`}>
            <div><strong>{business.name ?? "Unnamed mapped business"}</strong><span>{business.business_subtype} · {formatDistance(business.distance_m)}</span></div>
            <dl><dt>Address</dt><dd>{business.address ?? "Not mapped"}</dd><dt>Phone</dt><dd>{business.phone ?? "Not mapped"}</dd><dt>Opening hours</dt><dd>{business.opening_hours ?? "Not mapped"}</dd></dl>
          </article>
        )) : <p>No mapped competitors inside this radius.</p>}
      </div>
      <div className="access-evidence">
        <div><span>Nearest transit</span><strong>{analysis.nearest_transport?.name ?? "Not mapped"}</strong><small>{analysis.nearest_transport ? formatDistance(analysis.nearest_transport.distance_m) : "No mapped record"}</small></div>
        <div><span>Nearest major road</span><strong>{analysis.nearest_major_road?.name ?? "Not mapped"}</strong><small>{analysis.nearest_major_road ? formatDistance(analysis.nearest_major_road.distance_m) : "No mapped record"}</small></div>
      </div>
      <p className="coverage-note">{analysis.coverage.total_businesses.toLocaleString("id-ID")} competitors · {analysis.coverage.named_business_percent.toFixed(0)}% have mapped names</p>
    </section>
  );
}

export function formatDistance(distanceM: number) {
  return distanceM < 1000 ? `${Math.round(distanceM)} m` : `${(distanceM / 1000).toFixed(1)} km`;
}

function formatPeriod(value: string | null) {
  if (!value) return "Not mapped";
  return new Intl.DateTimeFormat("id-ID", { year: "numeric", month: "short" }).format(new Date(`${value}T00:00:00Z`));
}
