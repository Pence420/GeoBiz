# GeoBiz Data Platform Expansion Design

**Date:** 2026-10-01

**Status:** Proposed for implementation

**Scope:** Umbrella business taxonomy, detailed location evidence, on-demand refresh, offline DKI basemap, and browser E2E

## 1. Intent

GeoBiz will expand from three narrow business types into a broader, academically defensible location-intelligence product without introducing paid APIs or fabricated demo records. The user-facing business categories become F&B, Retail, and Services. Source-specific subtypes remain available for evidence and inspection.

The same promoted OpenStreetMap snapshot must power both business analysis and the offline basemap. A refresh is explicitly initiated by the operator and activates only after data, scores, and tiles pass their quality gates. The completed stack must be demonstrable without internet access after initial preparation.

## 2. Constraints

- DKI Jakarta remains the only supported geography.
- Demo and production-like records must be real and traceable to their source.
- Synthetic records remain restricted to isolated automated-test transactions.
- No paid API, API key, account, or billing dependency is introduced.
- Refresh is on-demand; no cron or long-running scheduler is added.
- Healthcare is not a selectable business category.
- Healthcare POIs remain supporting location evidence.
- Raw downloads and generated tile archives remain outside Git because of their size.
- Docker Compose remains the supported runtime and verification environment.

## 3. Non-goals

- No machine-learning recommendation model.
- No real-time traffic, footfall, population, or sales prediction.
- No nationwide coverage.
- No user accounts, payment system, or hosted deployment.
- No automated discovery of a newer official population period. A population release must be explicitly configured and verified.
- No claim that an opportunity score predicts commercial success.

## 4. Business taxonomy

### 4.1 Umbrella categories

The only active business-category slugs are:

| Slug | Display name | Included source concepts |
|---|---|---|
| `fnb` | F&B | restaurant, cafe, fast food, food court, bakery, confectionery, deli, coffee, ice cream |
| `retail` | Retail | supermarket, convenience, department store, variety store, clothes, shoes, electronics, mobile phone, furniture, books, stationery, cosmetics, jewellery, hardware, sports, toys, pet, car, motorcycle |
| `services` | Services | fitness centre, gym, hairdresser, beauty, barbershop, laundry, car wash, car repair, motorcycle repair, bicycle repair, travel agency, copy shop, printing |

Classification is allow-list based. A generic `shop=*` record is not accepted unless its value is explicitly mapped. Offices, government facilities, education, healthcare, accommodation, religious facilities, and industrial premises are never inferred as Services.

### 4.2 Subtypes

Every promoted business has one stable `business_subtype` selected by a versioned taxonomy rule. The subtype records the specific source concept, while `category_id` points to one umbrella category.

Examples:

- `amenity=restaurant` → `fnb` / `restaurant`
- `shop=bakery` → `fnb` / `bakery`
- `shop=supermarket` → `retail` / `supermarket`
- `shop=electronics` → `retail` / `electronics`
- `leisure=fitness_centre` → `services` / `fitness_centre`
- `shop=laundry` → `services` / `laundry`
- `shop=car_repair` → `services` / `car_repair`

When multiple supported tags exist, a deterministic priority list selects one subtype. The full original tag object remains stored so the decision can be audited. Ambiguous records that cannot be resolved deterministically are rejected and counted in the quality report.

### 4.3 Taxonomy versioning

The initial umbrella taxonomy version is `v2.0.0`. The version is stored on each business snapshot, returned by analysis and methodology APIs, and included in the dataset fingerprint. Changing a mapping rule requires a new taxonomy version and regeneration of profiles and opportunity scores.

## 5. Database changes

An Alembic migration will:

1. expand the category-slug constraint to permit the three legacy and three v2 slugs during the migration window;
2. upsert `fnb`, `retail`, and `services`, initially inactive, while the legacy release remains usable;
3. add `business_subtype text` and `taxonomy_version text`, backfill legacy rows from their existing categories, then make both columns non-null;
4. add an index on `(category_id, business_subtype, geom)` for subtype breakdowns and proximity queries;
5. add a `data_releases` table for cross-resource activation;
6. add `data_release_sources` to associate a release with its immutable source snapshots and their roles;
7. change dataset-source identity from unique `slug` to unique `(slug, sha256)` so a refresh inserts a new provenance row instead of overwriting the prior checksum and dates;
8. add a non-null `data_release_id` foreign key to businesses, POIs, roads, transport stops, administrative areas, normalization profiles, and opportunity scores;
9. include `data_release_id` in source-identity uniqueness constraints and lookup indexes so two retained releases may contain the same source record;
10. backfill every existing record and source association into a legacy v1 release and mark it active.

`data_releases` contains:

- immutable release ID;
- status: `staging`, `validated`, `active`, `failed`, or `superseded`;
- combined manifest and dataset fingerprint;
- taxonomy and scoring versions;
- immutable PMTiles filename and checksum;
- start, validation, activation, and failure timestamps;
- a structured error payload when failed.

Exactly one release is active. Existing `dataset_sources` and `import_runs` continue to record per-source provenance.

All runtime repository queries resolve the active release first and filter every release-bound table by its ID. Legacy businesses are not heuristically recategorized in place. The migration preserves them in the active v1 release, while the first v2 refresh builds a separate release from verified source tags. Activating v2 atomically activates the three umbrella categories and deactivates legacy categories. Until that succeeds, the current v1 application remains usable. The v2 frontend reports an upgrade-required state if it is started against the still-active v1 release rather than presenting mismatched results.

## 6. Scoring v2

Scoring version `v2.0.0` uses the existing normalized factors and incomplete-data semantics. Approved weights are:

| Factor | F&B | Retail | Services |
|---|---:|---:|---:|
| Population density | 0.20 | 0.25 | 0.25 |
| Competition | 0.20 | 0.20 | 0.20 |
| Public transport | 0.15 | 0.15 | 0.10 |
| Commercial activity | 0.15 | 0.20 | 0.15 |
| Office activity | 0.20 | 0.10 | 0.15 |
| Road accessibility | 0.10 | 0.10 | 0.15 |
| Healthcare proximity | 0.00 | 0.00 | 0.00 |

Healthcare POIs may be displayed in nearby evidence but do not affect these category scores. Competition counts all businesses in the selected umbrella category. Subtype composition is explanatory evidence and does not receive a separate weight in v2.

## 7. Detailed location evidence

The analysis response is extended with:

- `competitor_subtype_counts`: count by subtype inside the selected radius;
- `nearest_competitors`: up to ten real businesses ordered by geographic distance, each with name, subtype, distance, coordinates, and source identity;
- `nearest_transport`: nearest official stop or station with name, type, distance, and source identity;
- `nearest_major_road`: name, type, and distance when available;
- `poi_breakdown`: counts for commercial, office, education, and healthcare subtypes;
- `containing_area`: kelurahan, kecamatan from official joined properties, population, density, and observation period;
- `coverage`: named-business percentage and missing-source-field counts for the current selection;
- `taxonomy_version`, `scoring_version`, dataset fingerprint, source snapshot dates, and limitations.

Business GeoJSON and popups expose `business_subtype`, address fields, brand/operator, opening hours, phone, website, and source identity when present in original OSM tags. Missing attributes are shown as unavailable and are never invented.

Analytics adds category totals, subtype composition, score distribution, top opportunity areas, and coverage metrics. Methodology publishes the exact taxonomy mapping and scoring weights.

## 8. On-demand refresh architecture

### 8.1 Operator interface

The primary command is:

```bash
make refresh-data
```

Supporting commands are:

```bash
make refresh-data-dry-run
make prepare-offline-map
make refresh-status
```

The refresh command accepts explicit configuration through environment variables and a committed source configuration file. Credentials are not required for the approved public sources.

### 8.2 Refresh phases

1. **Preflight** — verify Docker services, disk space, source configuration, writable data directories, and database connectivity; acquire a PostgreSQL advisory lock.
2. **Download** — stream sources into a release-specific temporary directory, calculate SHA-256, record HTTP metadata, and reject empty or truncated responses.
3. **Manifest** — write timestamped manifests containing source URL, observed time when published, retrieval time, checksum, byte size, licence, and request parameters.
4. **Stage** — parse OSM businesses/context, DKI boundaries, GTFS, and configured population data without changing active tables.
5. **Validate** — apply geometry, identity, duplicate, boundary, category, name-coverage, administrative-join, and source-count gates.
6. **Build tiles** — generate an immutable DKI PMTiles archive from the same OSM PBF and verify representative tiles at low, medium, and high zooms.
7. **Derive** — generate v2 normalization profiles and all 267 × 3 × 5 opportunity observations in the release transaction.
8. **Activate** — promote staged tables and mark the release active in one database transaction after the immutable tile archive is already present and healthy.
9. **Retain** — keep the previous active release and tile archive as the immediate rollback target; keep at most two superseded release artifacts by default.

Network or validation failure leaves the active release unchanged. A failed refresh records a structured failure but never deletes the last working raw snapshot, database release, or tile archive.

### 8.3 Source behavior

- OpenStreetMap business, contextual, administrative, and basemap data share one Jakarta PBF checksum.
- TransJakarta GTFS is downloaded from the configured official static-feed URL.
- Population remains pinned to the explicitly configured official period unless the operator supplies a new source configuration and crosswalk.
- HTTP conditional requests may report an unchanged source. An unchanged full input set produces a no-op refresh rather than duplicate import runs.
- Source dates come from the publisher or source state metadata. Retrieval time is not presented as the source observation date.

## 9. Offline basemap

### 9.1 Generation

Tilemaker runs in a pinned container image and generates `data/tiles/releases/<release-id>.pmtiles`. The committed tilemaker JSON/Lua configuration includes DKI roads, waterways, buildings, land use, administrative labels, and relevant place labels. The existing DKI boundary provides the map coverage mask.

The archive is generated to a temporary filename, checksum-verified, then renamed to its immutable release filename. Generated archives are ignored by Git.

### 9.2 Serving

A small Docker `tiles` service serves immutable PMTiles files with byte-range support. The frontend registers the PMTiles MapLibre protocol and requests the tile URL belonging to the active data release.

The local MapLibre style is committed in the frontend. It uses:

- locally served vector tiles;
- a restrained high-contrast road and land-use palette consistent with the current dashboard;
- local system-font rendering by omitting external glyph endpoints;
- no remote sprites; required symbols are CSS or runtime-generated shapes;
- visible OpenStreetMap attribution.

The API exposes `/api/map-config` with the active release ID, tile URL, tile checksum, bounds, zoom limits, attribution, and fallback availability.

### 9.3 Fallback and failure

If no offline archive has ever been prepared, the map may use the existing OpenFreeMap style and displays a clear “online fallback” badge. After an offline archive exists, local tiles are the default. A tile failure offers retry and preserves non-map analysis results.

The offline E2E project blocks all non-local HTTP requests and must still render the basemap, labels, businesses, and analysis state.

## 10. API and frontend changes

### 10.1 API contracts

Category parameters accept only `fnb`, `retail`, and `services`. This is an intentional breaking v2 API change. Hidden v1 aliases are not retained because they would have ambiguous competition semantics.

Affected endpoints:

- `GET /api/business-categories`
- `GET /api/businesses`
- `POST /api/analyze-location`
- `GET /api/opportunity-map`
- `GET /api/area-rankings`
- `GET /api/analytics`
- `GET /api/methodology`
- `GET /api/search`

New endpoints:

- `GET /api/map-config`
- `GET /api/refresh-status`

Refresh execution remains a local CLI operation and is not exposed as an unauthenticated HTTP mutation.

### 10.2 Frontend

The category selector, rankings, comparison, analytics, and methodology views use the three umbrella categories. Business popups show subtype and available source attributes. The analysis sidebar gains subtype composition, nearest competitors, nearest transit, road evidence, and expanded area context.

Map initialization first requests `/api/map-config`. Offline and fallback states are visually distinct. Changing a category or radius retains the selected location and enabled layers.

## 11. Browser E2E

Playwright is added as a pinned development dependency and runs from a pinned Docker service. The command is:

```bash
make e2e
```

The default project targets Chromium for deterministic local grading and CI portability. Tests run against the live Compose frontend, backend, database, and tile service.

Required scenarios:

1. load Map Explorer and wait for the local map to become ready;
2. switch F&B, Retail, and Services and observe corresponding real record counts;
3. search for an area and a real business, select a result, and observe a recalculated score;
4. change radius and verify metric changes;
5. toggle business, heatmap, population, opportunity, transit, commercial, education, office, and road layers;
6. inspect a business popup with subtype and source identity;
7. filter opportunity areas and compare exactly three areas;
8. load Analytics and verify category/subtype evidence;
9. load Methodology and verify taxonomy, weights, source snapshots, and limitations;
10. simulate analysis and tile failures and verify recovery controls;
11. block every non-local network request and verify the complete offline path.

Tests use semantic roles and stable product-facing labels rather than CSS implementation selectors whenever possible. Test traces and screenshots are retained only on failure.

The local demo E2E suite reads the promoted real database. Synthetic test fixtures remain permitted only for isolated backend integration tests and are never promoted into the demo volume.

## 12. Quality gates

A refresh cannot activate unless:

- all three umbrella categories contain at least one record;
- every promoted business has source type, source ID, category, subtype, taxonomy version, and valid DKI geometry;
- duplicate source identities are zero;
- invalid geometry count is zero;
- all mapped subtype values are recognized by taxonomy v2;
- population administrative join rate is at least 95%;
- every configured opportunity scope contains exactly 267 area observations;
- scoring weights for each category total exactly 1.0;
- the PMTiles archive checksum matches the release record;
- representative vector tiles can be decoded;
- backend tests, frontend tests, production build, and browser E2E pass.

Counts are recorded and compared with the previous release. Large changes produce an explicit warning and require `--accept-count-change`; they are never silently accepted. The threshold is a 30% decrease or 100% increase for any umbrella category or primary supporting dataset.

## 13. Security and operational safety

- Download URLs are allow-listed in committed source configuration.
- Redirects to a different host are rejected unless explicitly configured.
- Downloads have byte limits, timeouts, and checksum verification.
- Archive paths are generated by the application and cannot contain user-controlled traversal segments.
- PostgreSQL advisory locking prevents concurrent refreshes.
- CLI output never prints environment secrets.
- The refresh CLI supports dry-run validation before promotion.
- Destructive cleanup never targets the active or immediately previous release.

## 14. Rollout and rollback

1. Apply the v2 schema migration.
2. Prepare an offline tile release from the current verified Jakarta PBF.
3. Run the first v2 refresh and review quality-count changes.
4. Activate the release and run backend, frontend, build, and E2E verification.
5. Commit code and small manifests/configuration; do not commit raw PBF or PMTiles artifacts.

Rollback marks the previous release active and restores its immutable tile URL. Schema downgrade is not required for release rollback. Code rollback across the v1/v2 API boundary requires restoring the corresponding database backup because category semantics changed intentionally.

## 15. Success criteria

The expansion is complete when:

1. users can analyze F&B, Retail, and Services across all supported radii;
2. every displayed business is traceable and exposes a specific subtype;
3. location analysis explains subtype mix and nearest real-world evidence;
4. `make refresh-data` creates or activates a release only after all gates pass;
5. a failed refresh leaves the previous release usable;
6. `make prepare-offline-map` creates a local DKI basemap from the verified OSM snapshot;
7. the dashboard works with external network requests blocked;
8. `make e2e` verifies the critical user journey against the live Docker stack;
9. methodology exposes taxonomy, scoring, datasets, dates, licences, fingerprints, and limitations;
10. no billing configuration or paid provider is required.
