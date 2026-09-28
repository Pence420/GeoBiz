# GeoBiz MVP Design Specification

**Status:** Proposed for user review  
**Date:** 2026-09-28  
**Product:** GeoBiz — GIS-Based Business Location Intelligence Platform

## 1. Purpose

GeoBiz is a university-project decision-support application for comparing the suitability of real locations in DKI Jakarta for opening a restaurant, gym, or pharmacy. It combines real-world business and public data with transparent spatial analysis to produce a Business Location Score from 0–100.

GeoBiz must demonstrate GIS concepts and provide an understandable analysis. It must not claim to predict business success.

## 2. Agreed constraints

- Initial coverage is DKI Jakarta.
- Initial business categories are restaurant, gym, and pharmacy.
- Every displayed business and every competitor used in demo scoring must be a traceable real-world record. Fabricated names, locations, and competitor counts are prohibited.
- Synthetic records may exist only in isolated automated tests and must never enter the demo database.
- Local deployment uses Docker Compose.
- The project must not require payment, a billing account, or a credit card.
- The map uses MapLibre GL JS with OpenFreeMap vector tiles and visible OpenStreetMap attribution.
- The interface follows the structure and visual language of the supplied Routeon logistics dashboard reference, adapted to GeoBiz rather than copying its branding or logistics content.
- Desktop is the primary presentation format. Smaller screens remain usable through collapsible panels, but a separate mobile application is out of scope.

## 3. MVP user journey

1. The user opens Map Explorer centered on DKI Jakarta.
2. The user chooses restaurant, gym, or pharmacy.
3. The user chooses an analysis radius: 500 m, 1 km, 2 km, 3 km, or 5 km. The default is 1 km.
4. The map renders the relevant competitor distribution and opportunity layer.
5. The user searches for a location or clicks directly on the map.
6. GeoBiz sends the coordinates, category, and radius to the analysis API.
7. PostGIS calculates nearby real businesses and relevant geographic factors.
8. The scoring engine normalizes factors using a versioned DKI Jakarta reference distribution and applies category-specific weights.
9. The interface shows the final score, interpretation label, factor breakdown, nearby insights, data date, and methodology link.
10. The user may add the result to an area comparison table.

## 4. Information architecture

### 4.1 Global header

- GeoBiz wordmark and compact symbol.
- Primary navigation: Map Explorer, Analytics, Methodology.
- Data snapshot indicator rather than authentication/profile controls.
- Search may live inside the map card on desktop to match the reference layout.

Authentication and user accounts are not part of the MVP.

### 4.2 Map Explorer

The desktop workspace uses a 12-column dashboard grid:

- Left eight columns: map card and area-ranking table.
- Right four columns: score and insight cards.
- Consistent 16–20 px gaps and subtle section boundaries.

The map card contains:

- Location search.
- Business-category segmented selector or compact select.
- Radius selector.
- Layer control.
- Fullscreen, zoom, and reset-to-Jakarta controls.
- Selected-location marker and analysis-radius circle.
- Competitor points/clusters.
- Optional competitor heatmap.
- Population and opportunity polygon layers.

### 4.3 Analysis cards

The right column contains:

1. **Business Location Score** — large score, opportunity label, selected category, and location/area name.
2. **Factor Breakdown** — horizontal bars for normalized factor scores. The factors shown change by category.
3. **Nearby Market Profile** — real counts for competitors, transit stops, commercial locations, offices, universities, and healthcare facilities as relevant.
4. **Data Confidence and Freshness** — source snapshot dates and a concise completeness disclaimer.

### 4.4 Area ranking and comparison

The lower-left panel replaces the reference dashboard's orders table:

- Ranked DKI Jakarta areas.
- Area name, final score, population score, competition score, access score, and action.
- Category and radius inherit the current map filters.
- Up to three areas can be pinned for comparison.
- Comparison is factor-by-factor and never invents missing metrics.

### 4.5 Analytics and methodology views

Analytics provides aggregate views only after the Map Explorer vertical slice works:

- Top opportunity areas.
- Distribution of businesses by category.
- Population versus competition plot.
- Dataset coverage and freshness summary.

Methodology explains sources, category mappings, factor definitions, weights, normalization, limitations, and attribution in language suitable for academic assessment.

## 5. Visual system

### 5.1 Direction

The visual direction is a clean operational dashboard:

- Neutral white and cool-gray surfaces.
- Near-black primary text.
- Electric blue as the main action and score accent.
- Restrained cyan/indigo may be used inside the main opportunity card and charts.
- Soft 10–14 px corner radii.
- One-pixel neutral borders with little or no elevation.
- Dense but readable spacing.
- Strong number typography for scores and statistics.
- Icons are simple outline glyphs; decorative illustrations are unnecessary.

The product should feel credible and analytical, not playful, futuristic, or like a generic admin template.

### 5.2 Map styling

Map clarity comes from vector data and label hierarchy rather than excessive decoration:

- OpenFreeMap supplies the vector basemap without an API key or billing account.
- MapLibre GL JS renders it with WebGL and high-DPI support.
- The base style uses light neutral land, pale blue-gray water, muted green parks, white local roads, and stronger primary roads.
- Basemap POIs that compete with GeoBiz overlays are hidden or reduced.
- District/subdistrict and major-road labels remain readable.
- GeoBiz layers have a clear z-order: base map, opportunity/population fills, roads if enabled, heatmap, clusters/points, selected location, labels/controls.
- The map always retains the required OpenStreetMap contributor attribution.

OpenFreeMap is an external free service provided as-is. The demo therefore requires internet access for basemap tiles. GeoBiz's application data and analysis run locally. A future self-hosted tile stack is out of MVP scope.

### 5.3 Opportunity colors

Use a sequential scale that remains distinguishable and does not imply false precision:

- 0–20: very low, light neutral-gray.
- >20–40: low, pale blue-gray.
- >40–60: moderate, light blue.
- >60–80: good, saturated blue.
- >80–100: high, deep electric blue.

Competition heatmaps use a separate warm scale and are never displayed at full opacity over opportunity polygons. Legends are mandatory.

### 5.4 Responsive behavior

- At wide desktop sizes, map and right analysis column remain visible together.
- At narrower laptop widths, the right column becomes slightly narrower and table columns collapse by priority.
- Below tablet width, the map occupies the viewport and analysis appears as a bottom sheet or drawer.
- Touch targets remain at least 44 px even though desktop density is compact.

## 6. Technical architecture

```text
Browser
  React + TypeScript + Vite
  MapLibre GL JS
  TanStack Query
  Tailwind CSS
          |
          | HTTP / GeoJSON
          v
FastAPI application
  API routes
  analysis service
  scoring service
  dataset metadata service
          |
          | SQL + spatial queries
          v
PostgreSQL + PostGIS
  application tables
  staging/import tables
  spatial indexes

Offline ETL commands
  BIG/Satu Data/BPS
  OSM/Overpass snapshots
  TransJakarta GTFS
          |
          v
validated PostGIS records
```

Docker Compose runs frontend, backend, database, and one-shot migration/import commands. Basemap tiles remain external and free.

## 7. Frontend modules

- `app-shell`: global header, navigation, and responsive workspace.
- `map-explorer`: owns MapLibre lifecycle and coordinates map interactions.
- `map-layers`: isolated source/layer definitions for opportunity, population, competitor, transport, and selection overlays.
- `analysis-controls`: category, radius, search, and layer visibility.
- `location-analysis`: score, factor bars, nearby counts, freshness, and loading/error/empty states.
- `area-ranking`: opportunity-area query and comparison selection.
- `analytics`: aggregate charts built from API data.
- `methodology`: static plus API-provided scoring/source metadata.
- `api-client`: typed API contracts and TanStack Query hooks.

Map rendering concerns must not be mixed into score-card components. The selected-analysis state is represented by coordinates, category, radius, and returned analysis ID/version.

## 8. Backend modules

- `categories`: category definitions and active scoring configuration.
- `businesses`: real business queries, bounding-box endpoints, and clustering-friendly responses.
- `pois`: supporting POI and transport queries.
- `areas`: administrative polygons, population, and opportunity output.
- `analysis`: spatial feature calculation for a selected coordinate/radius.
- `scoring`: pure factor normalization, weighting, labeling, and version metadata.
- `datasets`: source attribution, retrieval date, and quality metrics.
- `imports`: offline source-specific staging, normalization, validation, and promotion.

Routes delegate to services; spatial SQL remains encapsulated in repositories/query modules. Scoring must be independently testable without HTTP or a running map client.

## 9. Data model

Core tables:

- `business_categories`
- `businesses`
- `pois`
- `transport_stops`
- `administrative_areas`
- `roads`
- `scoring_weights`
- `normalization_profiles`
- `dataset_sources`
- `import_runs`
- optional `location_analysis_cache`

Every externally sourced feature includes:

- stable internal ID
- source provider
- source record ID
- source URL or dataset ID
- source observation/snapshot date where known
- retrieval timestamp
- original tags/properties in JSONB where useful
- geometry in EPSG:4326

Business uniqueness starts with `(source_provider, source_type, source_record_id)`. Additional name-and-distance matching flags possible duplicates for review; it must not merge records silently.

Spatial columns receive GiST indexes. Metre-based proximity uses PostGIS geography or an explicitly appropriate projected calculation.

## 10. Data acquisition and integrity

The accepted source strategy is defined in `docs/data-source-research.md`:

- BIG for administrative geometry.
- Satu Data Jakarta/BPS for population.
- OpenStreetMap snapshots for businesses, relevant POIs, commercial features, and roads.
- Official TransJakarta GTFS for bus stops/routes, with clearly labelled OSM supplementation for other rail transit only where required.

Request-time APIs never depend on a live Overpass query. Imports run offline and produce:

- source/checksum metadata
- record counts by type and area
- missing-name rates
- invalid-geometry counts
- duplicate candidates
- join coverage for population and administrative areas

The population-to-boundary join target is at least 95% of DKI kelurahan. Unmatched records are handled through a documented code/name crosswalk rather than being discarded silently.

## 11. Spatial analysis

For a clicked point and radius, the backend calculates:

- containing administrative area and population density
- same-category competitor count and optional distance weighting
- distinct public-transport stops/stations
- commercial land coverage and selected commercial POI density
- office activity proxy
- distance/access to selected road classes
- healthcare-facility proximity for pharmacies
- nearby universities/schools as an insight, initially not a weighted generic-category factor

Polygon POIs retain their original geometry. Representative points may be derived for proximity operations, but the transformation is documented.

## 12. Scoring

### 12.1 Normalization

Normalization is category-, radius-, dataset-, and version-specific:

1. Generate reference observations across DKI Jakarta using equal-area hex-cell centroids.
2. Calculate raw factors for each reference observation.
3. Winsorize each factor at its 5th and 95th percentiles.
4. Convert values to percentile ranks from 0–100.
5. Invert negative factors such as competition with `100 - percentile_rank`.
6. Store the profile, input dataset versions, radius, and calculation timestamp.

A factor score of 80 means the location scores above approximately 80% of the reference observations for that factor. It does not mean an 80% probability of success.

### 12.2 Initial weights

| Factor | Restaurant | Gym | Pharmacy |
|---|---:|---:|---:|
| Population density | 20% | 30% | 25% |
| Low competition | 20% | 20% | 15% |
| Public transport | 15% | 10% | 10% |
| Commercial activity | 15% | 10% | 10% |
| Office activity proxy | 20% | 15% | 5% |
| Road accessibility | 10% | 15% | 10% |
| Healthcare proximity | 0% | 0% | 25% |
| **Total** | **100%** | **100%** | **100%** |

Weights live in data, not hard-coded branching logic. Each analysis response identifies the scoring version used.

### 12.3 Labels

- 0–20: Very Low
- >20–40: Low
- >40–60: Moderate
- >60–80: Good
- >80–100: High

These are presentation bands, not confidence intervals.

## 13. API surface

Initial endpoints:

- `GET /api/health`
- `GET /api/business-categories`
- `GET /api/businesses?category=&bbox=&limit=`
- `GET /api/poi?type=&bbox=&limit=`
- `GET /api/areas?bbox=`
- `POST /api/analyze-location`
- `GET /api/opportunity-map?business_category=&radius=`
- `GET /api/area-rankings?business_category=&radius=&limit=`
- `GET /api/methodology`
- `GET /api/datasets`

Map-heavy endpoints return GeoJSON or vector-friendly compact responses. Pagination/limits and bounding-box filters are mandatory for feature endpoints.

An analysis response contains final score, label, normalized scores, raw nearby metrics, weights, containing area, data snapshot dates, scoring version, and a limitations message.

## 14. Loading, empty, and error states

- The initial map displays skeleton cards until category/area metadata is ready.
- Selecting a point retains the prior map view while the analysis card shows an in-place loading state.
- A failed analysis leaves the selected point visible and presents a retry action.
- Missing factor data is shown as unavailable; it is never replaced with zero or fabricated data.
- If a required factor is unavailable, the API returns an explicit incomplete-analysis status rather than silently reweighting.
- Basemap failure does not erase loaded GeoBiz results; the UI explains that the free external map service is unavailable.
- Search failures suggest clicking the map directly.

## 15. Accessibility

- Controls and cards use semantic HTML outside the MapLibre canvas.
- All controls are keyboard reachable and visibly focused.
- Color is never the sole encoding; labels and numerical values accompany choropleths and bars.
- Contrast targets WCAG AA.
- Map legends and selected-location summaries have text equivalents.
- Reduced-motion preferences disable nonessential transitions.

## 16. Testing and verification

### Backend

- Unit tests for normalization, inverse scoring, weights, labels, and incomplete factors.
- PostGIS integration tests for radius boundaries, point-in-polygon, distance, and deduplication.
- Contract tests for API schemas and dataset metadata.
- Import tests using small fixed source excerpts; synthetic test fixtures remain isolated from demo data.

### Frontend

- Component tests for controls, score states, legends, errors, and comparison limits.
- API-hook tests with mocked contracts.
- Map-layer tests for source/layer configuration and interaction state.
- End-to-end flow: select category, click location, receive analysis, inspect source metadata, add comparison.
- Responsive and keyboard checks for desktop and drawer layouts.

### Data quality

- Assert that every demo business has source provenance and valid geometry.
- Report category counts and missing-name rates.
- Verify population join coverage reaches the 95% target.
- Validate all scoring weights sum to 1.0 per category/version.
- Record and expose the normalization profile version.

## 17. Delivery sequence

1. Repository and Docker foundation.
2. PostGIS schema, migrations, and source metadata.
3. Real-data spike for DKI restaurant/gym/pharmacy plus boundary/population join.
4. Backend spatial vertical slice.
5. Scoring reference profiles and transparent methodology response.
6. Frontend dashboard shell and free vector basemap.
7. End-to-end clicked-location analysis.
8. Opportunity choropleth, ranking, and comparison.
9. Analytics/methodology views, accessibility, performance, and demo polish.

The real-data spike is a gate: the project does not proceed by substituting fabricated demo records if a source is incomplete.

## 18. Out of scope

- Authentication and accounts
- Payments or paid APIs
- Mobile application
- Machine-learning recommendations
- Chatbot
- Real-time traffic or population
- Property/rental pricing
- Route optimization
- Microservices, Kafka, or distributed infrastructure
- Claims of causal business-success prediction
- Production-grade self-hosted global basemap infrastructure

## 19. Acceptance criteria

The MVP is accepted when:

1. Docker Compose starts the application and PostGIS locally.
2. The dashboard visually follows the approved Routeon-inspired structure while using GeoBiz branding and content.
3. The map is a crisp, interactive vector map of DKI Jakarta and requires no paid account.
4. A user can select restaurant, gym, or pharmacy and choose an analysis radius.
5. The map shows traceable real competitors and relevant GIS layers.
6. Clicking a location returns a reproducible 0–100 score with factor breakdown and raw nearby metrics.
7. The UI shows source/snapshot metadata and an honest limitations statement.
8. Opportunity areas can be ranked and up to three areas compared.
9. No fabricated business is present in the demo database.
10. Automated tests cover scoring and core spatial behavior, and data-quality checks pass.
