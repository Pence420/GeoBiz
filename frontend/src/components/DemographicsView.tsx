import { useEffect, useMemo, useState } from "react";
import type { Geometry } from "geojson";

import {
  fetchDemographics,
  fetchPopulationLayer,
  type Demographics,
  type MapLayerFeature,
} from "../lib/api";

const number = (value: number) => value.toLocaleString("id-ID");

function polygonRings(geometry: Geometry): number[][][][] {
  if (geometry.type === "Polygon") return [geometry.coordinates];
  if (geometry.type === "MultiPolygon") return geometry.coordinates;
  return [];
}

function mapGeometry(features: MapLayerFeature[]) {
  const coordinates = features.flatMap((feature) =>
    polygonRings(feature.geometry).flatMap((polygon) => polygon.flatMap((ring) => ring)),
  );
  if (!coordinates.length) return { paths: new Map<number, string>(), markers: new Map<number, [number, number]>() };
  let west = Infinity;
  let east = -Infinity;
  let south = Infinity;
  let north = -Infinity;
  for (const [longitude, latitude] of coordinates) {
    west = Math.min(west, longitude);
    east = Math.max(east, longitude);
    south = Math.min(south, latitude);
    north = Math.max(north, latitude);
  }
  const scale = Math.min(600 / Math.max(east - west, 0.001), 390 / Math.max(north - south, 0.001));
  const offsetX = (640 - (east - west) * scale) / 2;
  const offsetY = (430 - (north - south) * scale) / 2;
  const point = ([longitude, latitude]: number[]): [number, number] =>
    [offsetX + (longitude - west) * scale, offsetY + (north - latitude) * scale];
  const xy = (coordinate: number[]) => point(coordinate).map((value) => value.toFixed(1)).join(",");
  const paths = new Map(features.map((feature) => [
    feature.id,
    polygonRings(feature.geometry).map((polygon) =>
      polygon.map((ring) => `M${ring.map(xy).join("L")}Z`).join(""),
    ).join(""),
  ]));
  const markers = new Map(features.flatMap((feature) => {
    const coordinate = polygonRings(feature.geometry)[0]?.[0]?.[0];
    return coordinate ? [[feature.id, point(coordinate)] as [number, [number, number]]] : [];
  }));
  return { paths, markers };
}

export function DemographicsView({ releaseId }: { releaseId: number }) {
  const [data, setData] = useState<Demographics | null>(null);
  const [features, setFeatures] = useState<MapLayerFeature[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [region, setRegion] = useState("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchDemographics(), fetchPopulationLayer(releaseId)])
      .then(([response, layer]) => {
        if (cancelled) return;
        if (response.release_id !== releaseId) {
          setError("Rilis data berubah saat halaman dimuat. Muat ulang halaman untuk menyamakan peta dan angka.");
          return;
        }
        setData(response);
        setFeatures(layer);
      })
      .catch((reason: Error) => { if (!cancelled) setError(reason.message); });
    return () => { cancelled = true; };
  }, [releaseId]);

  const regions = useMemo(() => [...new Set(data?.areas.map((area) => area.wilayah) ?? [])].sort(), [data]);
  const visibleAreas = useMemo(() => data?.areas.filter((area) => region === "all" || area.wilayah === region) ?? [], [data, region]);
  const islandAreas = useMemo(() => visibleAreas.filter((area) => area.wilayah.includes("KEP. SERIBU")), [visibleAreas]);
  const mainlandAreas = useMemo(() => visibleAreas.filter((area) => !area.wilayah.includes("KEP. SERIBU")), [visibleAreas]);
  const primaryAreas = mainlandAreas.length ? mainlandAreas : islandAreas;
  const primaryIds = useMemo(() => new Set(primaryAreas.map((area) => area.id)), [primaryAreas]);
  const islandIds = useMemo(() => new Set(islandAreas.map((area) => area.id)), [islandAreas]);
  const primaryMap = useMemo(() => mapGeometry(features.filter((feature) => primaryIds.has(feature.id))), [features, primaryIds]);
  const islandMap = useMemo(() => mapGeometry(features.filter((feature) => islandIds.has(feature.id))), [features, islandIds]);
  const selected = visibleAreas.find((area) => area.id === selectedId) ?? null;
  const maxAge = Math.max(1, ...(data?.age_gender.map((band) => Math.max(band.male, band.female)) ?? []));
  const renderArea = (area: Demographics["areas"][number], path: string) => <path key={area.id} d={path} fillRule="evenodd" className={`demographics-area ${selectedId === area.id ? "selected" : ""}`} data-density={area.population_density == null ? "none" : area.population_density >= 30000 ? "high" : area.population_density >= 15000 ? "medium" : "low"} onClick={() => setSelectedId(area.id)}><title>{area.name}: {number(area.population)} penduduk; {area.population_density?.toLocaleString("id-ID", { maximumFractionDigits: 0 }) ?? "—"} jiwa/km²</title></path>;
  const renderIslandMarker = (area: Demographics["areas"][number], point: [number, number]) => <circle key={area.id} cx={point[0]} cy={point[1]} r={selectedId === area.id ? 8 : 6} className="demographics-island-marker" data-density={area.population_density == null ? "none" : area.population_density >= 30000 ? "high" : area.population_density >= 15000 ? "medium" : "low"} onClick={() => setSelectedId(area.id)}><title>{area.name}: {number(area.population)} penduduk</title></circle>;

  return (
    <main id="main-content" className="content-view demographics-view" aria-label="Demografi penduduk wilayah">
      <header className="demographics-heading">
        <div><span>DKI JAKARTA · DATA PENDUDUK RESMI</span><h1>People behind the place.</h1><p>Struktur usia dan persebaran penduduk per kelurahan—konteks lokasi, bukan profil pelanggan bisnis.</p></div>
        <label>Fokus peta<select value={region} onChange={(event) => { setRegion(event.target.value); setSelectedId(null); }}><option value="all">Seluruh DKI Jakarta</option>{regions.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
      </header>
      {error ? <div className="view-error" role="alert"><strong>Demographics belum tersedia</strong><p>{error}</p></div> : null}
      {!data && !error ? <div className="view-loading" role="status">Memuat demografi penduduk…</div> : null}
      {data ? <>
        {data.covered_areas < data.total_areas ? <p className="demographics-warning" role="status">Rincian umur dan jenis kelamin tersedia untuk {number(data.covered_areas)} dari {number(data.total_areas)} kelurahan. Total di bawah hanya menghitung wilayah yang tercakup.</p> : null}
        <section className="demographics-stats" aria-label="Ringkasan penduduk">
          <article><span>Penduduk DKI tercakup</span><strong>{number(data.total_population)}</strong><small>{number(data.covered_areas)} kelurahan · periode {data.observed_at?.slice(0, 4) ?? "tidak diketahui"}</small></article>
          <article><span>Laki-laki</span><strong>{number(data.male)}</strong><small>{data.total_population ? (data.male / data.total_population * 100).toFixed(1) : "0"}% dari penduduk tercakup</small></article>
          <article><span>Perempuan</span><strong>{number(data.female)}</strong><small>{data.total_population ? (data.female / data.total_population * 100).toFixed(1) : "0"}% dari penduduk tercakup</small></article>
        </section>
        <div className="demographics-grid">
          <section className="demographics-panel age-panel" aria-label="Distribusi umur dan jenis kelamin">
            <div className="demographics-title"><div><span>01 / PEOPLE</span><h2>Age & gender</h2><p>Jumlah penduduk DKI menurut kelompok umur.</p></div><div className="age-legend"><span><i className="male-key" />Laki-laki</span><span><i className="female-key" />Perempuan</span></div></div>
            {data.age_gender.length ? <div className="age-chart" role="table" aria-label="Jumlah penduduk menurut umur dan jenis kelamin">
              {data.age_gender.map((band) => <div className="age-row" role="row" key={band.age}><span>{band.age}</span><div className="age-bars"><i className="male-bar" style={{ width: `${band.male / maxAge * 100}%` }} /><i className="female-bar" style={{ width: `${band.female / maxAge * 100}%` }} /></div><strong>{number(band.total)}</strong></div>)}
            </div> : <p className="panel-empty">Rincian umur belum tersedia dalam snapshot ini.</p>}
          </section>
          <section className="demographics-panel residence-panel" aria-label="Peta persebaran penduduk">
            <div className="demographics-title"><div><span>02 / PLACE</span><h2>Population by kelurahan</h2><p>Warna lebih pekat berarti kepadatan lebih tinggi.</p></div><span>{number(visibleAreas.length)} area</span></div>
            {primaryMap.paths.size ? <div className="demographics-map-wrap">
              <svg className="demographics-map" viewBox="0 0 640 430" aria-hidden="true">
                {primaryAreas.map((area) => { const path = primaryMap.paths.get(area.id); return path ? renderArea(area, path) : null; })}
                {!mainlandAreas.length ? islandAreas.map((area) => { const point = primaryMap.markers.get(area.id); return point ? renderIslandMarker(area, point) : null; }) : null}
              </svg>
              {mainlandAreas.length > 0 && islandMap.paths.size > 0 ? <div className="demographics-island-inset"><span>Kepulauan Seribu</span><svg viewBox="0 0 640 430" aria-hidden="true">
                {islandAreas.map((area) => { const path = islandMap.paths.get(area.id); return path ? renderArea(area, path) : null; })}
                {islandAreas.map((area) => { const point = islandMap.markers.get(area.id); return point ? renderIslandMarker(area, point) : null; })}
              </svg><small>6 kelurahan · skala terpisah</small></div> : null}
            </div> : <p className="panel-empty">Geometri wilayah belum tersedia.</p>}
            <div className="map-density-legend"><span><i className="low" />&lt;15 ribu</span><span><i className="medium" />15–30 ribu</span><span><i className="high" />≥30 ribu jiwa/km²</span></div>
            <p className="selection-help" id="demographics-selection-help">Pilih wilayah pada peta, atau gunakan daftar Kelurahan dengan keyboard.</p>
            <div className="selected-demographic" aria-live="polite">
              <label htmlFor="demographic-area-select">Kelurahan</label>
              <select id="demographic-area-select" aria-describedby="demographics-selection-help" value={selectedId ?? ""} onChange={(event) => setSelectedId(event.target.value ? Number(event.target.value) : null)}><option value="">Pilih wilayah</option>{visibleAreas.map((area) => <option value={area.id} key={area.id}>{area.name} · {area.kecamatan}</option>)}</select>
              {selected ? <span><strong>{number(selected.population)} penduduk</strong> · {selected.population_density?.toLocaleString("id-ID", { maximumFractionDigits: 0 }) ?? "—"} jiwa/km²</span> : <span>Pilih di peta atau daftar untuk melihat rinciannya.</span>}
            </div>
          </section>
        </div>
        <footer className="view-provenance">Sumber: <a href={data.source_url} target="_blank" rel="noreferrer">Satu Data Jakarta / Dukcapil DKI</a> · Periode {data.observed_at?.slice(0, 4) ?? "—"} · Rilis {data.release_key} · Dataset {data.dataset_fingerprint.slice(0, 16)}. Penduduk wilayah tidak sama dengan pelanggan atau pengunjung.</footer>
      </> : null}
    </main>
  );
}
