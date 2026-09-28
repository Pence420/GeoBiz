# GeoBiz MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Dockerized GeoBiz MVP that uses traceable real-world DKI Jakarta data to analyze restaurant, gym, and pharmacy locations on a crisp free vector map.

**Architecture:** A React/Vite dashboard consumes typed FastAPI endpoints backed by PostgreSQL/PostGIS. Offline import commands stage, validate, and promote government, OpenStreetMap, and GTFS snapshots; request-time analysis never calls external data APIs. Scoring uses versioned DKI-wide percentile profiles and returns both normalized scores and raw evidence.

**Tech Stack:** React, TypeScript, Vite, Tailwind CSS, TanStack Query, MapLibre GL JS, OpenFreeMap, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL/PostGIS, pytest, Vitest, Playwright, Docker Compose

**Spec:** `docs/superpowers/specs/2026-09-28-geobiz-mvp-design.md`

## Global Constraints

- Coverage is DKI Jakarta only.
- Supported categories are exactly `restaurant`, `gym`, and `pharmacy` for this MVP.
- Demo businesses must be real-world records with source provenance; fabricated demo records are prohibited.
- Synthetic records are permitted only inside isolated automated tests.
- No service may require payment, a billing account, or a credit card.
- MapLibre GL JS renders OpenFreeMap vector tiles with visible OpenStreetMap attribution.
- Runtime spatial analysis uses local PostGIS data and never calls Overpass.
- Frontend presentation follows the approved Routeon-inspired dashboard structure using GeoBiz branding.
- Desktop is primary; narrow screens use a map-first drawer layout.
- Missing required factor data produces an explicit incomplete result, never zero substitution or silent reweighting.

## Review Focus

- A click outside DKI Jakarta must return a typed `LOCATION_OUTSIDE_COVERAGE` response and leave the UI usable.
- Duplicate OSM representations of one business must be flagged or deduplicated without silently merging unrelated nearby businesses.
- A normalization profile for the wrong radius, category, or dataset version must never be reused.
- A missing required factor must return `incomplete`, show the unavailable factor, and must not produce a misleading final score.
- Basemap/network failure must preserve already loaded GeoBiz analysis and show a specific basemap warning.

---

## Planned file structure

```text
.
├── .env.example                         # documented local settings, no secrets
├── Makefile                             # repeatable developer commands
├── compose.yaml                         # db, backend, frontend services
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/                    # schema migrations
│   ├── app/
│   │   ├── main.py                      # FastAPI composition only
│   │   ├── core/config.py               # validated environment settings
│   │   ├── db/session.py                # engine/session lifecycle
│   │   ├── db/models.py                 # persistence models
│   │   ├── api/errors.py                # typed domain-to-HTTP errors
│   │   ├── api/routes/                  # categories, map, analysis, metadata
│   │   ├── categories/service.py        # supported-category lookup
│   │   ├── analysis/contracts.py        # request/response schemas
│   │   ├── analysis/repository.py       # spatial query boundary
│   │   ├── analysis/service.py          # analysis orchestration
│   │   ├── scoring/domain.py             # pure score types and rules
│   │   ├── scoring/service.py            # profile selection and scoring
│   │   ├── datasets/service.py           # provenance/freshness output
│   │   └── imports/                      # source-specific offline ETL
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── fixtures/                    # tiny labelled test-only records
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── app/                         # app shell, routes, query client
│   │   ├── api/                         # shared generated/manual contracts
│   │   ├── features/map-explorer/       # map lifecycle and layers
│   │   ├── features/analysis/           # controls, score, evidence
│   │   ├── features/areas/              # rankings and comparison
│   │   ├── features/analytics/          # aggregate charts
│   │   ├── features/methodology/        # sources and scoring explanation
│   │   └── styles/                      # tokens and global styles
│   ├── tests/
│   └── e2e/
├── data/
│   ├── README.md                        # raw data policy; raw artifacts ignored
│   ├── manifests/                       # committed checksums and source metadata
│   └── crosswalks/                      # reviewed administrative aliases
└── docs/
    └── demo-runbook.md                  # repeatable setup and presentation flow
```

## Task 1: Dockerized application foundation

**Files:**
- Create: `.env.example`
- Create: `.gitignore`
- Create: `Makefile`
- Create: `compose.yaml`
- Create: `backend/Dockerfile`
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/tests/unit/test_health.py`
- Create: `frontend/Dockerfile`
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/app/App.tsx`
- Create: `frontend/src/styles/index.css`
- Create: `frontend/src/app/App.test.tsx`

**Interfaces:**
- Consumes: none.
- Produces: `GET /api/health -> {"status":"ok"}`, runnable backend/frontend/database services, and standard `make` commands used by every later task.

- [ ] **Step 1: Write the failing backend health test**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the backend test and verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_health.py -v`

Expected: FAIL because the backend package and app are not implemented.

- [ ] **Step 3: Implement the minimal FastAPI application and validated settings**

```python
# backend/app/main.py
from fastapi import FastAPI

app = FastAPI(title="GeoBiz API", version="0.1.0")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

```python
# backend/app/core/config.py
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://geobiz:geobiz@db:5432/geobiz"
    cors_origins: list[str] = ["http://localhost:5173"]
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Write and run the failing frontend smoke test**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("renders the GeoBiz product name", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "GeoBiz" })).toBeVisible();
  });
});
```

Run: `cd frontend && npm test -- --run src/app/App.test.tsx`

Expected: FAIL until `App` and the test configuration exist.

- [ ] **Step 5: Implement the frontend entry point and smoke screen**

```tsx
// frontend/src/app/App.tsx
export function App() {
  return (
    <main>
      <h1>GeoBiz</h1>
      <p>DKI Jakarta business location intelligence</p>
    </main>
  );
}
```

- [ ] **Step 6: Add Compose and repeatable commands**

`compose.yaml` must define:

- `db`: `postgis/postgis:17-3.5`, named volume, healthcheck using `pg_isready`.
- `backend`: Python 3.12 image build, port `8000`, waits for healthy database.
- `frontend`: Node 22 image build, port `5173`, `VITE_API_BASE_URL=http://localhost:8000/api`.

`Makefile` must expose `up`, `down`, `logs`, `migrate`, `test-backend`, `test-frontend`, `test`, and `lint` without destructive cleanup commands.

- [ ] **Step 7: Verify the foundation**

Run: `docker compose config`

Expected: configuration resolves with no error and no paid API key variable.

Run: `cd backend && python -m pytest -v`

Expected: PASS.

Run: `cd frontend && npm test -- --run`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add .env.example .gitignore Makefile compose.yaml backend frontend
git commit -m "build: scaffold GeoBiz application"
```

## Task 2: PostGIS schema and provenance model

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_initial_schema.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/db/models.py`
- Create: `backend/tests/integration/conftest.py`
- Create: `backend/tests/integration/test_schema.py`

**Interfaces:**
- Consumes: `Settings.database_url` from Task 1.
- Produces: SQLAlchemy models `BusinessCategory`, `DatasetSource`, `ImportRun`, `AdministrativeArea`, `Business`, `Poi`, `TransportStop`, `Road`, `ScoringWeight`, and `NormalizationProfile`; `get_session()` dependency.

- [ ] **Step 1: Write the failing schema integration test**

```python
from sqlalchemy import text


def test_spatial_schema_has_provenance_and_gist_indexes(db_session) -> None:
    extension = db_session.scalar(
        text("SELECT extname FROM pg_extension WHERE extname = 'postgis'")
    )
    business_columns = {
        row[0]
        for row in db_session.execute(
            text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'businesses'
            """)
        )
    }
    indexes = {
        row[0]
        for row in db_session.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = 'businesses'")
        )
    }

    assert extension == "postgis"
    assert {"source_id", "source_record_id", "retrieved_at", "geom"} <= business_columns
    assert "ix_businesses_geom_gist" in indexes
```

- [ ] **Step 2: Run the schema test and verify it fails**

Run: `docker compose up -d db && cd backend && python -m pytest tests/integration/test_schema.py -v`

Expected: FAIL because migrations and tables do not exist.

- [ ] **Step 3: Define focused persistence models**

Use these required invariants:

```python
class Business(Base):
    __tablename__ = "businesses"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "source_type", "source_record_id",
            name="uq_business_source_record",
        ),
        Index("ix_businesses_geom_gist", "geom", postgresql_using="gist"),
    )

    id: Mapped[UUID]
    name: Mapped[str | None]
    category_id: Mapped[UUID]
    source_id: Mapped[UUID]
    source_type: Mapped[str]
    source_record_id: Mapped[str]
    source_observed_at: Mapped[date | None]
    retrieved_at: Mapped[datetime]
    original_tags: Mapped[dict]
    geom: Mapped[WKBElement]  # Geometry(geometry_type="POINT", srid=4326)
```

Administrative areas use `MULTIPOLYGON,4326`; roads use `MULTILINESTRING,4326`. `NormalizationProfile` has a unique constraint on `(category_id, radius_m, dataset_fingerprint, version)` and stores percentile breakpoints as JSONB.

- [ ] **Step 4: Create the initial Alembic migration**

The migration must:

- enable `postgis` and `pgcrypto`;
- create every core table;
- constrain business category slugs to the three seeded categories;
- add foreign keys and GiST indexes;
- add a check that active category weights total validation is enforced by application service, with each individual weight in `[0,1]`;
- seed restaurant, gym, and pharmacy categories without seeding any business.

- [ ] **Step 5: Apply migrations and run the integration test**

Run: `docker compose run --rm backend alembic upgrade head`

Expected: migration succeeds.

Run: `cd backend && python -m pytest tests/integration/test_schema.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic.ini backend/alembic backend/app/db backend/tests/integration
git commit -m "feat: add PostGIS schema and provenance"
```

## Task 3: Real-data import framework and quality gates

**Files:**
- Create: `data/README.md`
- Create: `data/manifests/.gitkeep`
- Create: `data/crosswalks/dki_kelurahan_aliases.csv`
- Create: `backend/app/imports/contracts.py`
- Create: `backend/app/imports/manifest.py`
- Create: `backend/app/imports/osm.py`
- Create: `backend/app/imports/administrative.py`
- Create: `backend/app/imports/population.py`
- Create: `backend/app/imports/gtfs.py`
- Create: `backend/app/imports/quality.py`
- Create: `backend/app/imports/cli.py`
- Create: `backend/tests/unit/imports/test_osm_mapping.py`
- Create: `backend/tests/unit/imports/test_quality.py`
- Create: `backend/tests/integration/test_import_promotion.py`

**Interfaces:**
- Consumes: persistence models from Task 2 and manually downloaded/source-provided files.
- Produces: `ImportManifest`, `ImportQualityReport`, CLI commands `python -m app.imports.cli ...`, and promoted traceable records.

- [ ] **Step 1: Write failing OSM mapping and duplicate tests**

```python
def test_maps_supported_real_business_tags() -> None:
    assert classify_osm_tags({"amenity": "restaurant"}) == "restaurant"
    assert classify_osm_tags({"leisure": "fitness_centre"}) == "gym"
    assert classify_osm_tags({"amenity": "pharmacy"}) == "pharmacy"
    assert classify_osm_tags({"healthcare": "pharmacy"}) == "pharmacy"


def test_same_source_record_is_duplicate_but_nearby_branch_is_not() -> None:
    existing = SourceIdentity("osm", "node", "123")
    assert is_exact_duplicate(existing, SourceIdentity("osm", "node", "123"))
    assert not is_exact_duplicate(existing, SourceIdentity("osm", "node", "124"))
```

- [ ] **Step 2: Run the import unit tests and verify they fail**

Run: `cd backend && python -m pytest tests/unit/imports -v`

Expected: FAIL because import contracts and mapping functions do not exist.

- [ ] **Step 3: Implement manifest and mapping contracts**

```python
class ImportManifest(BaseModel):
    dataset_slug: str
    source_name: str
    source_url: HttpUrl
    source_license: str
    source_observed_at: date | None
    retrieved_at: datetime
    sha256: str
    local_filename: str


class ImportQualityReport(BaseModel):
    total_records: int
    promoted_records: int
    invalid_geometry_count: int
    missing_name_count: int
    exact_duplicate_count: int
    duplicate_candidate_count: int
    administrative_join_rate: float | None
    failures: list[str]
```

The import refuses files without a matching manifest/checksum. Raw downloaded files live under ignored `data/raw/`; only manifests, crosswalks, and aggregate quality reports are committed.

- [ ] **Step 4: Implement source adapters and staging validation**

- OSM adapter accepts GeoJSON produced from an explicitly saved Overpass query, retains OSM element type/ID and original tags, clips to DKI, and maps only documented categories.
- Administrative adapter validates/repairs polygon geometry, keeps official codes, and filters DKI.
- Population adapter normalizes region codes/names and joins via code first, reviewed alias second.
- GTFS adapter reads `stops.txt`, retains agency/source identity, and groups child platforms by `parent_station` when present.
- Promotion runs in one database transaction; a failed quality gate leaves production tables unchanged.

- [ ] **Step 5: Encode quality gates and tests**

```python
def assert_demo_quality(report: ImportQualityReport) -> None:
    if report.invalid_geometry_count:
        raise ImportQualityError("invalid geometries must be resolved before promotion")
    if (
        report.administrative_join_rate is not None
        and report.administrative_join_rate < 0.95
    ):
        raise ImportQualityError("population join coverage must be at least 95%")
```

The integration test must prove that a rejected batch does not partially promote and that exact duplicate source records cannot be inserted twice.

- [ ] **Step 6: Run tests**

Run: `cd backend && python -m pytest tests/unit/imports tests/integration/test_import_promotion.py -v`

Expected: PASS.

- [ ] **Step 7: Perform and document the real-data spike**

Run source-specific commands against the downloaded DKI artifacts:

```bash
docker compose run --rm backend python -m app.imports.cli stage-osm data/raw/dki-businesses.geojson --manifest data/manifests/osm-dki.json
docker compose run --rm backend python -m app.imports.cli validate latest
docker compose run --rm backend python -m app.imports.cli promote latest
docker compose run --rm backend python -m app.imports.cli report latest
```

Expected report:

- non-zero real record counts for restaurant, gym, and pharmacy;
- every promoted record has provider/type/record ID;
- invalid geometry count is zero;
- population join rate is at least 95%;
- missing-name and duplicate-candidate counts are reported, not hidden.

If a source cannot meet the gate, stop and update the source/crosswalk. Do not generate substitute businesses.

- [ ] **Step 8: Commit**

```bash
git add data/README.md data/manifests data/crosswalks backend/app/imports backend/tests/unit/imports backend/tests/integration/test_import_promotion.py
git commit -m "feat: add traceable GIS data imports"
```

## Task 4: Pure scoring domain and versioned profiles

**Files:**
- Create: `backend/app/scoring/domain.py`
- Create: `backend/app/scoring/service.py`
- Create: `backend/app/scoring/profiles.py`
- Create: `backend/tests/unit/scoring/test_domain.py`
- Create: `backend/tests/unit/scoring/test_profiles.py`
- Create: `backend/alembic/versions/0002_seed_scoring_weights.py`

**Interfaces:**
- Consumes: `ScoringWeight` and `NormalizationProfile` models from Task 2.
- Produces: `score_location(category_slug, radius_m, dataset_fingerprint, raw_factors) -> ScoreResult`.

- [ ] **Step 1: Write failing score behavior tests**

```python
def test_weighted_score_and_inverse_competition() -> None:
    profile = profile_for_test(
        percentiles={"population": [10, 20, 30], "competition": [1, 3, 8]}
    )
    result = score_location(
        category_slug="restaurant",
        radius_m=1000,
        dataset_fingerprint=profile.dataset_fingerprint,
        raw_factors={"population": 30, "competition": 1, **complete_restaurant_factors()},
        profile=profile,
        weights=restaurant_weights(),
    )
    assert result.normalized_factors["population"] == 100
    assert result.normalized_factors["competition"] == 100
    assert 0 <= result.final_score <= 100


def test_missing_required_factor_is_incomplete_not_zero() -> None:
    result = score_with_missing_factor("population")
    assert result.status == "incomplete"
    assert result.final_score is None
    assert result.missing_factors == ["population"]


def test_profile_must_match_category_radius_and_dataset() -> None:
    with pytest.raises(ProfileMismatchError):
        score_with_profile(radius_m=500, profile_radius_m=1000)
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd backend && python -m pytest tests/unit/scoring -v`

Expected: FAIL because scoring types and services do not exist.

- [ ] **Step 3: Implement typed scoring domain**

```python
class ScoreResult(BaseModel):
    status: Literal["complete", "incomplete"]
    final_score: float | None
    label: Literal["Very Low", "Low", "Moderate", "Good", "High"] | None
    raw_factors: dict[str, float | None]
    normalized_factors: dict[str, float | None]
    weights: dict[str, float]
    missing_factors: list[str]
    scoring_version: str
    profile_id: UUID
```

Implement percentile interpolation, 5th/95th winsorization values from the stored profile, inverse competition, stable rounding to one decimal, and the approved label bands.

- [ ] **Step 4: Seed approved category weights**

Migration `0002` inserts the exact weight table from the spec. Its upgrade validates that weights sum to `1.0` per category; downgrade removes only that version's weights.

- [ ] **Step 5: Run score tests and migration verification**

Run: `cd backend && python -m pytest tests/unit/scoring -v`

Expected: PASS.

Run: `docker compose run --rm backend alembic upgrade head`

Expected: PASS with three valid category weight sets.

- [ ] **Step 6: Commit**

```bash
git add backend/app/scoring backend/tests/unit/scoring backend/alembic/versions/0002_seed_scoring_weights.py
git commit -m "feat: add transparent location scoring"
```

## Task 5: Spatial analysis repository and service

**Files:**
- Create: `backend/app/analysis/contracts.py`
- Create: `backend/app/analysis/repository.py`
- Create: `backend/app/analysis/service.py`
- Create: `backend/tests/integration/test_spatial_analysis.py`
- Create: `backend/tests/unit/analysis/test_service.py`

**Interfaces:**
- Consumes: PostGIS tables from Task 2 and `score_location` from Task 4.
- Produces: `AnalysisService.analyze(request: AnalyzeLocationRequest) -> AnalyzeLocationResponse`.

- [ ] **Step 1: Write failing spatial boundary tests**

```python
def test_radius_includes_point_on_boundary(spatial_repository, seeded_spatial_data) -> None:
    metrics = spatial_repository.calculate_metrics(
        longitude=106.8,
        latitude=-6.2,
        category_slug="restaurant",
        radius_m=1000,
    )
    assert metrics.competitor_count == seeded_spatial_data.expected_inclusive_count


def test_point_outside_dki_is_rejected(analysis_service) -> None:
    with pytest.raises(LocationOutsideCoverageError) as error:
        analysis_service.analyze(request_at(longitude=110.0, latitude=-7.0))
    assert error.value.code == "LOCATION_OUTSIDE_COVERAGE"
```

- [ ] **Step 2: Run analysis tests and verify they fail**

Run: `cd backend && python -m pytest tests/integration/test_spatial_analysis.py tests/unit/analysis/test_service.py -v`

Expected: FAIL because the repository and service do not exist.

- [ ] **Step 3: Define analysis contracts**

```python
class AnalyzeLocationRequest(BaseModel):
    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]
    business_category: Literal["restaurant", "gym", "pharmacy"]
    radius_m: Literal[500, 1000, 2000, 3000, 5000] = 1000


class NearbyMetrics(BaseModel):
    competitor_count: int
    transport_stop_count: int
    commercial_poi_count: int
    office_count: int
    university_count: int
    healthcare_count: int
    population_density: float | None
    nearest_major_road_m: float | None
```

`AnalyzeLocationResponse` includes coordinates, containing area, nearby metrics, `ScoreResult`, source snapshots, and limitations.

- [ ] **Step 4: Implement parameterized PostGIS queries**

Use `ST_Covers` for DKI containment and `ST_DWithin(geom::geography, point::geography, :radius_m)` for metre-based proximity. Group transport child platforms by station identity. Return commercial land coverage separately from POI counts. Never interpolate missing population.

- [ ] **Step 5: Implement service orchestration**

The service validates DKI coverage, obtains current dataset fingerprint, calculates raw metrics, selects an exact matching normalization profile, scores the result, and attaches source metadata. A missing required profile is a typed service-unavailable error, not an on-demand profile calculation.

- [ ] **Step 6: Run tests**

Run: `cd backend && python -m pytest tests/integration/test_spatial_analysis.py tests/unit/analysis/test_service.py -v`

Expected: PASS, including radius-boundary and outside-DKI cases.

- [ ] **Step 7: Commit**

```bash
git add backend/app/analysis backend/tests/integration/test_spatial_analysis.py backend/tests/unit/analysis
git commit -m "feat: analyze DKI business locations"
```

## Task 6: Public API contracts and map queries

**Files:**
- Create: `backend/app/api/errors.py`
- Create: `backend/app/api/routes/categories.py`
- Create: `backend/app/api/routes/businesses.py`
- Create: `backend/app/api/routes/areas.py`
- Create: `backend/app/api/routes/analysis.py`
- Create: `backend/app/api/routes/metadata.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/unit/api/test_contracts.py`
- Create: `backend/tests/integration/test_api.py`

**Interfaces:**
- Consumes: services from Tasks 3–5.
- Produces: documented `/api` endpoints consumed by the frontend.

- [ ] **Step 1: Write failing API contract tests**

```python
def test_analyze_location_contract(client) -> None:
    response = client.post(
        "/api/analyze-location",
        json={
            "latitude": -6.2,
            "longitude": 106.8,
            "business_category": "restaurant",
            "radius_m": 1000,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["score"]["scoring_version"]
    assert body["nearby_metrics"]["competitor_count"] >= 0
    assert body["sources"]


def test_outside_coverage_has_typed_error(client) -> None:
    response = client.post(
        "/api/analyze-location",
        json={"latitude": -7, "longitude": 110, "business_category": "gym", "radius_m": 1000},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "LOCATION_OUTSIDE_COVERAGE"
```

- [ ] **Step 2: Run API tests and verify they fail**

Run: `cd backend && python -m pytest tests/unit/api tests/integration/test_api.py -v`

Expected: FAIL because routes are not registered.

- [ ] **Step 3: Implement routes and consistent errors**

All errors follow:

```json
{
  "error": {
    "code": "LOCATION_OUTSIDE_COVERAGE",
    "message": "GeoBiz currently analyzes locations inside DKI Jakarta only.",
    "details": {}
  }
}
```

Feature endpoints require valid `bbox` and enforce a maximum limit. Business responses include source provider/type/record ID, display name, category, and geometry. Methodology and dataset endpoints expose current versions and attribution.

- [ ] **Step 4: Register routers and CORS**

Compose routers in `main.py`; do not put query logic in route functions. Configure only the origins from validated settings.

- [ ] **Step 5: Run contract, API, and OpenAPI checks**

Run: `cd backend && python -m pytest tests/unit/api tests/integration/test_api.py -v`

Expected: PASS.

Run: `python -c 'from app.main import app; assert "/api/analyze-location" in app.openapi()["paths"]'`

Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api backend/app/main.py backend/tests/unit/api backend/tests/integration/test_api.py
git commit -m "feat: expose GeoBiz spatial API"
```

## Task 7: Dashboard shell and design system

**Files:**
- Create: `frontend/src/styles/tokens.css`
- Modify: `frontend/src/styles/index.css`
- Create: `frontend/src/app/AppShell.tsx`
- Create: `frontend/src/app/Navigation.tsx`
- Create: `frontend/src/app/routes.tsx`
- Create: `frontend/src/features/map-explorer/MapExplorerPage.tsx`
- Create: `frontend/src/features/analysis/AnalysisPanel.tsx`
- Create: `frontend/src/features/areas/AreaRankingPanel.tsx`
- Modify: `frontend/src/app/App.tsx`
- Create: `frontend/src/app/AppShell.test.tsx`

**Interfaces:**
- Consumes: no backend data yet; uses explicit empty/loading component states.
- Produces: approved responsive 12-column dashboard layout and reusable visual tokens.

- [ ] **Step 1: Write failing layout and accessibility tests**

```tsx
it("exposes primary navigation and analysis regions", () => {
  render(<AppShell />);
  expect(screen.getByRole("navigation", { name: "Primary" })).toBeVisible();
  expect(screen.getByRole("main")).toBeVisible();
  expect(screen.getByRole("complementary", { name: "Location analysis" })).toBeVisible();
});

it("labels the current data snapshot without a fake user profile", () => {
  render(<AppShell />);
  expect(screen.getByText(/data snapshot/i)).toBeVisible();
  expect(screen.queryByText(/dispatch officer/i)).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd frontend && npm test -- --run src/app/AppShell.test.tsx`

Expected: FAIL because the dashboard shell does not exist.

- [ ] **Step 3: Define design tokens**

```css
:root {
  --color-bg: #f3f4f6;
  --color-surface: #ffffff;
  --color-surface-muted: #f7f7f8;
  --color-text: #0a0a0b;
  --color-text-muted: #74767c;
  --color-border: #e6e7ea;
  --color-primary: #2450e6;
  --color-primary-strong: #0820a6;
  --radius-card: 14px;
  --space-grid: 18px;
  --focus-ring: 0 0 0 3px rgb(36 80 230 / 28%);
}
```

Use a system-first sans-serif font stack until a redistributable selected font is intentionally added. Do not fetch fonts from a paid service.

- [ ] **Step 4: Implement the responsive shell**

Build semantic header/nav/main/aside regions. Desktop uses an 8/4 grid, the map card has a stable minimum height, and narrow layouts turn analysis into a labelled drawer with 44 px controls. Use border and spacing hierarchy instead of heavy shadows.

- [ ] **Step 5: Run component and static checks**

Run: `cd frontend && npm test -- --run src/app/AppShell.test.tsx`

Expected: PASS.

Run: `cd frontend && npm run lint && npm run typecheck`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat: build GeoBiz dashboard shell"
```

## Task 8: Free vector map and interaction state

**Files:**
- Create: `frontend/src/features/map-explorer/mapConfig.ts`
- Create: `frontend/src/features/map-explorer/GeoBizMap.tsx`
- Create: `frontend/src/features/map-explorer/layers.ts`
- Create: `frontend/src/features/map-explorer/useMapSelection.ts`
- Create: `frontend/src/features/map-explorer/MapControls.tsx`
- Modify: `frontend/src/features/map-explorer/MapExplorerPage.tsx`
- Create: `frontend/src/features/map-explorer/GeoBizMap.test.tsx`
- Create: `frontend/src/features/map-explorer/layers.test.ts`

**Interfaces:**
- Consumes: OpenFreeMap style URL and GeoJSON API shapes from Task 6.
- Produces: `MapSelection { longitude, latitude, radiusM }`, layer visibility state, and `onSelectLocation(selection)` callback.

- [ ] **Step 1: Write failing map configuration tests**

```ts
it("uses the free basemap and mandatory OSM attribution", () => {
  expect(MAP_STYLE_URL).toMatch(/^https:\/\/tiles\.openfreemap\.org\//);
  expect(OSM_ATTRIBUTION).toContain("OpenStreetMap contributors");
});

it("keeps selected location above analytic overlays", () => {
  const ids = buildGeoBizLayers().map((layer) => layer.id);
  expect(ids.indexOf("selected-location")).toBeGreaterThan(ids.indexOf("competitor-points"));
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd frontend && npm test -- --run src/features/map-explorer`

Expected: FAIL because map configuration does not exist.

- [ ] **Step 3: Implement MapLibre map lifecycle**

Initialize one map instance, center on DKI Jakarta, add navigation/fullscreen controls, preserve attribution, and dispose the map on unmount. A click emits coordinates only after the map is loaded. Draw a selected-location point and radius circle as GeoJSON sources.

- [ ] **Step 4: Implement analytic sources and layers**

Define typed layer builders for opportunity fill, population fill, competitor heatmap, clusters, individual competitors, transport points, selection radius, and selection marker. Each layer has a stable ID and legend definition. Basemap label visibility is adjusted only after style load.

- [ ] **Step 5: Handle basemap failure without discarding analysis**

```tsx
it("shows a basemap warning while preserving analysis children", async () => {
  render(<GeoBizMap analysisOverlay={<div>Score 82</div>} mapFactory={failingMapFactory} />);
  expect(await screen.findByText(/basemap is temporarily unavailable/i)).toBeVisible();
  expect(screen.getByText("Score 82")).toBeVisible();
});
```

Implement a non-blocking warning and retry control; do not clear React analysis state on MapLibre errors.

- [ ] **Step 6: Run tests and checks**

Run: `cd frontend && npm test -- --run src/features/map-explorer && npm run typecheck`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/map-explorer
git commit -m "feat: add free interactive vector map"
```

## Task 9: End-to-end location analysis experience

**Files:**
- Create: `frontend/src/api/contracts.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/features/analysis/useLocationAnalysis.ts`
- Create: `frontend/src/features/analysis/AnalysisControls.tsx`
- Create: `frontend/src/features/analysis/ScoreCard.tsx`
- Create: `frontend/src/features/analysis/FactorBreakdown.tsx`
- Create: `frontend/src/features/analysis/NearbyProfile.tsx`
- Create: `frontend/src/features/analysis/DataFreshness.tsx`
- Modify: `frontend/src/features/analysis/AnalysisPanel.tsx`
- Modify: `frontend/src/features/map-explorer/MapExplorerPage.tsx`
- Create: `frontend/src/features/analysis/AnalysisPanel.test.tsx`
- Create: `frontend/src/features/analysis/useLocationAnalysis.test.tsx`

**Interfaces:**
- Consumes: `POST /api/analyze-location`, `GET /api/business-categories`, `GET /api/businesses`, and map selection from Task 8.
- Produces: complete/incomplete/error analysis states rendered from typed contracts.

- [ ] **Step 1: Define contracts matching OpenAPI and write failing UI tests**

```ts
export type AnalysisStatus = "complete" | "incomplete";

export interface ScoreResult {
  status: AnalysisStatus;
  final_score: number | null;
  label: "Very Low" | "Low" | "Moderate" | "Good" | "High" | null;
  raw_factors: Record<string, number | null>;
  normalized_factors: Record<string, number | null>;
  weights: Record<string, number>;
  missing_factors: string[];
  scoring_version: string;
}
```

```tsx
it("never displays a score for incomplete analysis", () => {
  render(<AnalysisPanel result={incompleteResult({ missing: ["population"] })} />);
  expect(screen.queryByText(/\/ 100/)).not.toBeInTheDocument();
  expect(screen.getByText(/population data is unavailable/i)).toBeVisible();
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd frontend && npm test -- --run src/features/analysis`

Expected: FAIL because contracts and components do not exist.

- [ ] **Step 3: Implement typed API client and query hooks**

`analyzeLocation` sends coordinates/category/radius and parses non-2xx responses into `ApiError { code, message, details }`. The query key contains all four inputs. Requests are disabled before a location is selected. Prior successful data remains visible during refetch with an explicit updating state.

- [ ] **Step 4: Implement controls and score evidence cards**

Render category/radius controls, final score, label, normalized factor bars, raw nearby counts, source dates, scoring version, attribution, and methodology link. Every bar includes visible text. Loading skeletons preserve layout. Error states offer retry and keep the selected point.

- [ ] **Step 5: Connect competitor data and map analysis**

Fetch businesses for the current viewport/category with a bounded `bbox` and limit. Render source-backed records only. Popup fields include display name or “Unnamed mapped facility,” category, and source identity; never invent a business label.

- [ ] **Step 6: Run tests and checks**

Run: `cd frontend && npm test -- --run src/features/analysis src/features/map-explorer`

Expected: PASS.

Run: `cd frontend && npm run lint && npm run typecheck`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api frontend/src/features/analysis frontend/src/features/map-explorer
git commit -m "feat: connect location analysis dashboard"
```

## Task 10: Opportunity map, rankings, and comparison

**Files:**
- Create: `backend/app/areas/contracts.py`
- Create: `backend/app/areas/repository.py`
- Create: `backend/app/areas/service.py`
- Create: `backend/tests/integration/test_area_rankings.py`
- Modify: `backend/app/api/routes/areas.py`
- Create: `frontend/src/features/areas/useAreaRankings.ts`
- Create: `frontend/src/features/areas/AreaRankingTable.tsx`
- Create: `frontend/src/features/areas/AreaComparison.tsx`
- Modify: `frontend/src/features/areas/AreaRankingPanel.tsx`
- Modify: `frontend/src/features/map-explorer/layers.ts`
- Create: `frontend/src/features/areas/AreaRankingTable.test.tsx`

**Interfaces:**
- Consumes: versioned profiles/scoring from Task 4 and administrative areas from Task 2.
- Produces: opportunity GeoJSON, ranked area summaries, and a maximum-three comparison model.

- [ ] **Step 1: Write failing ranking and comparison tests**

```python
def test_rankings_are_descending_and_versioned(area_service) -> None:
    result = area_service.rank(category_slug="gym", radius_m=1000, limit=10)
    assert [item.final_score for item in result.items] == sorted(
        [item.final_score for item in result.items], reverse=True
    )
    assert result.scoring_version
```

```tsx
it("limits comparison to three areas", async () => {
  render(<AreaRankingTable areas={fourAreas} />);
  await user.click(screen.getByLabelText("Compare Area A"));
  await user.click(screen.getByLabelText("Compare Area B"));
  await user.click(screen.getByLabelText("Compare Area C"));
  expect(screen.getByLabelText("Compare Area D")).toBeDisabled();
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd backend && python -m pytest tests/integration/test_area_rankings.py -v`

Run: `cd frontend && npm test -- --run src/features/areas`

Expected: both FAIL because area services/components are incomplete.

- [ ] **Step 3: Implement versioned area scoring**

Use one documented representative observation strategy per kelurahan for MVP and store calculation metadata. Return FeatureCollection properties containing area ID/name, final score, label, scoring version, and data fingerprint. Do not imply uniform suitability across the polygon.

- [ ] **Step 4: Implement ranking table and comparison**

The table inherits category/radius, formats scores consistently, supports keyboard selection, and limits comparison to three. Comparison shows the same normalized factors and flags unavailable values rather than substituting zero.

- [ ] **Step 5: Add opportunity layer and legend**

Use the approved five-band sequential blue scale with borders and a text legend. Selecting a polygon opens its ranking summary and permits detailed centroid analysis with an explicit representative-point label.

- [ ] **Step 6: Run tests**

Run: `cd backend && python -m pytest tests/integration/test_area_rankings.py -v`

Run: `cd frontend && npm test -- --run src/features/areas src/features/map-explorer`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/areas backend/app/api/routes/areas.py backend/tests/integration/test_area_rankings.py frontend/src/features/areas frontend/src/features/map-explorer/layers.ts
git commit -m "feat: rank and compare opportunity areas"
```

## Task 11: Analytics, methodology, and provenance UI

**Files:**
- Create: `backend/app/analytics/service.py`
- Create: `backend/app/api/routes/analytics.py`
- Create: `backend/tests/integration/test_analytics_api.py`
- Create: `frontend/src/features/analytics/AnalyticsPage.tsx`
- Create: `frontend/src/features/analytics/OpportunityChart.tsx`
- Create: `frontend/src/features/analytics/DistributionChart.tsx`
- Create: `frontend/src/features/methodology/MethodologyPage.tsx`
- Create: `frontend/src/features/methodology/SourceTable.tsx`
- Modify: `frontend/src/app/routes.tsx`
- Create: `frontend/src/features/methodology/MethodologyPage.test.tsx`

**Interfaces:**
- Consumes: aggregate database queries and `/api/methodology`, `/api/datasets`.
- Produces: honest aggregate analytics and an auditable methodology page.

- [ ] **Step 1: Write failing provenance presentation test**

```tsx
it("shows source, snapshot, scoring version, and limitations", () => {
  render(<MethodologyPage data={methodologyFixture} />);
  expect(screen.getByText("OpenStreetMap")).toBeVisible();
  expect(screen.getByText(/snapshot/i)).toBeVisible();
  expect(screen.getByText(/scoring version/i)).toBeVisible();
  expect(screen.getByText(/does not predict business success/i)).toBeVisible();
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd frontend && npm test -- --run src/features/methodology`

Expected: FAIL because methodology components do not exist.

- [ ] **Step 3: Implement aggregate API with explicit definitions**

Return top opportunity areas, business counts by category, population-versus-competition observations, and dataset coverage metrics. Every metric includes a definition and dataset fingerprint. Aggregate queries never expose a fake “revenue” metric copied from the visual reference.

- [ ] **Step 4: Implement analytics and methodology routes**

Use lightweight SVG/CSS charts or a free open-source chart library already approved in dependencies. Include text/table equivalents for charts. The methodology page renders category weights, normalization explanation, source links/licenses, snapshot dates, and limitations.

- [ ] **Step 5: Run tests and accessibility checks**

Run: `cd backend && python -m pytest tests/integration/test_analytics_api.py -v`

Run: `cd frontend && npm test -- --run src/features/analytics src/features/methodology`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/analytics backend/app/api/routes/analytics.py backend/tests/integration/test_analytics_api.py frontend/src/features/analytics frontend/src/features/methodology frontend/src/app/routes.tsx
git commit -m "feat: explain GeoBiz insights and methodology"
```

## Task 12: End-to-end verification and academic demo runbook

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/location-analysis.spec.ts`
- Create: `frontend/e2e/responsive.spec.ts`
- Create: `backend/tests/integration/test_demo_data_integrity.py`
- Create: `docs/demo-runbook.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: complete application from Tasks 1–11.
- Produces: verified Docker demo, reproducible setup instructions, and integrity evidence.

- [ ] **Step 1: Write the failing demo-data integrity test**

```python
def test_every_demo_business_is_traceable(db_session) -> None:
    invalid_count = db_session.scalar(text("""
        SELECT count(*) FROM businesses
        WHERE source_id IS NULL
           OR source_record_id IS NULL
           OR retrieved_at IS NULL
           OR ST_IsValid(geom) = false
    """))
    assert invalid_count == 0


def test_no_synthetic_provider_exists_in_demo_database(db_session) -> None:
    count = db_session.scalar(text("""
        SELECT count(*) FROM dataset_sources
        WHERE lower(provider) IN ('fake', 'fixture', 'synthetic', 'seed')
    """))
    assert count == 0
```

- [ ] **Step 2: Write the failing browser journey**

```ts
test("analyzes a real Jakarta location and exposes evidence", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Business category").selectOption("restaurant");
  await page.getByLabel("Analysis radius").selectOption("1000");
  await page.getByTestId("map").click({ position: { x: 480, y: 320 } });
  await expect(page.getByRole("heading", { name: /business location score/i })).toBeVisible();
  await expect(page.getByText(/scoring version/i)).toBeVisible();
  await expect(page.getByText(/OpenStreetMap contributors/i)).toBeVisible();
});
```

- [ ] **Step 3: Run integrity and browser tests and verify any gaps**

Run: `cd backend && python -m pytest tests/integration/test_demo_data_integrity.py -v`

Run: `cd frontend && npx playwright test`

Expected before final wiring: one or more failures that identify missing demo/runtime details.

- [ ] **Step 4: Complete the runbook and README**

Document exact commands for environment setup, Docker startup, migrations, raw-data placement, manifest verification, import validation/promotion, normalization profile generation, test execution, and demo reset without destructive filesystem commands. Include:

- zero-billing statement;
- internet requirement for OpenFreeMap tiles;
- dataset licenses and attribution;
- snapshot dates and known limitations;
- a five-minute academic demonstration script;
- troubleshooting for unavailable basemap, failed population join, missing profile, and occupied ports.

- [ ] **Step 5: Run the complete quality gate**

Run: `docker compose config`

Run: `docker compose up -d --build`

Run: `make migrate`

Run: `make test`

Run: `make lint`

Run: `cd frontend && npx playwright test`

Expected: all commands pass; the app loads at `http://localhost:5173`, API docs at `http://localhost:8000/docs`, and no configuration requests a paid service key.

- [ ] **Step 6: Perform manual visual and GIS verification**

Verify at desktop and narrow viewport:

- visual hierarchy matches the approved dashboard direction;
- map labels remain crisp at common Jakarta zoom levels;
- attribution is always visible;
- all five map bands and legends are understandable without color alone;
- map selection, radius, competitor points, score, and evidence agree;
- basemap failure warning preserves existing analysis;
- keyboard focus order and drawer behavior are usable.

- [ ] **Step 7: Commit**

```bash
git add frontend/playwright.config.ts frontend/e2e backend/tests/integration/test_demo_data_integrity.py docs/demo-runbook.md README.md
git commit -m "test: verify GeoBiz academic demo"
```

## Completion gate

Before declaring the MVP complete:

- [ ] Confirm all ten acceptance criteria in the spec with evidence.
- [ ] Confirm the demo database contains no synthetic businesses.
- [ ] Confirm data-source and scoring versions appear in the UI and API.
- [ ] Confirm all three categories have non-zero real-business coverage or explicitly stop for source correction.
- [ ] Confirm no paid key, billing setup, or paid-provider dependency appears in configuration or documentation.
- [ ] Review the full branch against `docs/superpowers/specs/2026-09-28-geobiz-mvp-design.md`.
