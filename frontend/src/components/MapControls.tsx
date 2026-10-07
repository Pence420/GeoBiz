import { SearchBox } from "./SearchBox";
import type { BusinessCategory } from "../lib/api";

export type LayerKey = "opportunity" | "competitors" | "heatmap" | "population" | "transport" | "commercial" | "education" | "office" | "roads";
export type LayerState = Record<LayerKey, boolean>;

export type MapControlsProps = {
  category: BusinessCategory;
  radius: number;
  layers: LayerState;
  minimumScore: number;
  maximumCompetition: number | null;
  minimumPopulation: number;
  visibleAreas: number;
  onSelectLocation: (longitude: number, latitude: number) => void;
  onCategoryChange: (value: BusinessCategory) => void;
  onRadiusChange: (value: number) => void;
  onLayersChange: (value: LayerState) => void;
  onMinimumScoreChange: (value: number) => void;
  onMaximumCompetitionChange: (value: number | null) => void;
  onMinimumPopulationChange: (value: number) => void;
};

const layerLabels: Record<LayerKey, string> = {
  opportunity: "Opportunity",
  competitors: "Competitors",
  heatmap: "Heatmap",
  population: "Population",
  transport: "Transit",
  commercial: "Commercial",
  education: "Education",
  office: "Offices",
  roads: "Road network",
};

export function MapControls({
  category,
  radius,
  layers,
  minimumScore,
  maximumCompetition,
  minimumPopulation,
  visibleAreas,
  onSelectLocation,
  onCategoryChange,
  onRadiusChange,
  onLayersChange,
  onMinimumScoreChange,
  onMaximumCompetitionChange,
  onMinimumPopulationChange,
}: MapControlsProps) {
  return (
    <div className="map-toolbar" aria-label="Map search and controls">
      <SearchBox onSelect={onSelectLocation} />
      <label className="select-control">
        <span>Bisnis</span>
        <select value={category} onChange={(event) => onCategoryChange(event.target.value as BusinessCategory)}>
          <option value="fnb">F&B</option>
          <option value="retail">Retail</option>
          <option value="services">Services</option>
        </select>
      </label>
      <label className="select-control radius-control">
        <span>Radius</span>
        <select value={radius} onChange={(event) => onRadiusChange(Number(event.target.value))}>
          {[500, 1000, 2000, 3000, 5000].map((value) => <option key={value} value={value}>{value < 1000 ? "500 m" : `${value / 1000} km`}</option>)}
        </select>
      </label>
      <div className="toolbar-actions">
        <details className="toolbar-panel">
          <summary>Layers</summary>
          <div className="toolbar-panel-content layer-options">
            <strong>Map layers</strong>
            {(Object.keys(layerLabels) as LayerKey[]).map((layer) => (
              <label key={layer}>
                <input type="checkbox" checked={layers[layer]} onChange={() => onLayersChange({ ...layers, [layer]: !layers[layer] })} />
                <span>{layerLabels[layer]}</span>
              </label>
            ))}
          </div>
        </details>
        <details className="toolbar-panel">
          <summary>Filters</summary>
          <div className="toolbar-panel-content filter-options">
            <strong>Opportunity filters</strong>
            <label>Minimum score
              <select value={minimumScore} onChange={(event) => onMinimumScoreChange(Number(event.target.value))}>
                {[0, 40, 60, 80].map((value) => <option value={value} key={value}>{value === 0 ? "All scores" : `${value}+`}</option>)}
              </select>
            </label>
            <label>Competitors
              <select value={maximumCompetition ?? "all"} onChange={(event) => onMaximumCompetitionChange(event.target.value === "all" ? null : Number(event.target.value))}>
                <option value="all">Any density</option><option value="0">None</option><option value="5">At most 5</option><option value="10">At most 10</option><option value="25">At most 25</option>
              </select>
            </label>
            <label>Population
              <select value={minimumPopulation} onChange={(event) => onMinimumPopulationChange(Number(event.target.value))}>
                <option value="0">Any density</option><option value="10000">10,000+ / km²</option><option value="25000">25,000+ / km²</option><option value="40000">40,000+ / km²</option>
              </select>
            </label>
            <span>{visibleAreas} areas visible</span>
          </div>
        </details>
      </div>
    </div>
  );
}
