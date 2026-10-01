# GeoBiz Data Platform Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace narrow business types with traceable F&B, Retail, and Services umbrellas, add detailed location evidence, build an atomic on-demand refresh pipeline, serve a local DKI basemap, and verify the live Docker stack with Playwright.

**Architecture:** Every spatial row belongs to an immutable data release. A refresh stages and validates public data plus a PMTiles artifact before one transaction activates the release; runtime queries always filter by the active release. The frontend consumes v2 API contracts and a release-specific local basemap, while Playwright exercises the complete Compose stack with external networking blocked.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL 17/PostGIS 3.5, Alembic, React, TypeScript, MapLibre GL JS, PMTiles 4.5.0, tilemaker 3.2.0, Martin 1.16.1, Playwright 1.63.0, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-01-geobiz-data-platform-expansion-design.md`

## Global Constraints

- DKI Jakarta is the only supported geography.
- Active business categories are exactly `fnb`, `retail`, and `services`; healthcare remains supporting evidence only.
- Demo data must be real and traceable; synthetic records stay inside isolated tests.
- Taxonomy and scoring versions are both `v2.0.0`.
- Supported radii remain exactly 500, 1000, 2000, 3000, and 5000 metres.
- Refresh is operator-triggered through `make refresh-data`; no scheduler is introduced.
- No paid API, key, account, or billing configuration is allowed.
- Raw PBF, temporary downloads, and PMTiles archives remain ignored by Git.
- All commands and tests run through Docker Compose.

## Review Focus

- A refresh that loses network access after staging must leave the old release active; Task 6 adds the rollback integration test.
- One OSM feature matching multiple taxonomy rules must resolve deterministically or be rejected; Task 2 pins both outcomes.
- Runtime queries must never mix rows from two retained releases; Task 3 adds cross-release isolation tests.
- A missing/corrupt PMTiles file must select an explicit online fallback without discarding analysis state; Tasks 7 and 8 exercise this path.
- External network requests must be zero in offline mode, including glyphs, sprites, styles, and tiles; Task 10 enforces request blocking.

---

### Task 1: Introduce immutable data releases

**Files:**
- Create: `backend/alembic/versions/0004_data_releases_and_umbrella_categories.py`
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/datasets/service.py`
- Test: `backend/tests/integration/test_data_releases.py`

**Interfaces:**
- Consumes: existing SQLAlchemy models and `current_dataset_fingerprint(session)`.
- Produces: `DataRelease`, `DataReleaseSource`, `active_release(session) -> DataRelease`, and `active_release_id(session) -> int`.

- [ ] **Step 1: Write failing release-model integration tests**

```python
def test_database_rejects_two_active_releases(db_session):
    make_release(db_session, status="active", fingerprint="a" * 64)
    db_session.flush()
    make_release(db_session, status="active", fingerprint="b" * 64)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_active_release_returns_the_single_active_row(db_session):
    release = make_release(db_session, status="active", fingerprint="a" * 64)
    db_session.flush()
    assert active_release(db_session).id == release.id


def test_source_snapshots_are_immutable_per_checksum(db_session):
    one = make_source(db_session, slug="osm-dki", sha256="a" * 64)
    two = make_source(db_session, slug="osm-dki", sha256="b" * 64)
    db_session.flush()
    assert one.id != two.id
```

- [ ] **Step 2: Run the tests and verify the schema is missing**

Run: `docker compose run --rm backend pytest tests/integration/test_data_releases.py -q`

Expected: FAIL because `DataRelease`, release helpers, and migration `0004` do not exist.

- [ ] **Step 3: Add release models and active-release helpers**

Add models with these exact fields:

```python
class DataRelease(Base):
    __tablename__ = "data_releases"
    id: Mapped[int]
    release_key: Mapped[str]
    status: Mapped[str]
    dataset_fingerprint: Mapped[str]
    taxonomy_version: Mapped[str]
    scoring_version: Mapped[str]
    combined_manifest: Mapped[dict[str, Any]]
    tile_filename: Mapped[str | None]
    tile_sha256: Mapped[str | None]
    failure: Mapped[dict[str, Any] | None]
    validated_at: Mapped[datetime | None]
    activated_at: Mapped[datetime | None]


class DataReleaseSource(Base):
    __tablename__ = "data_release_sources"
    data_release_id: Mapped[int]
    dataset_source_id: Mapped[int]
    role: Mapped[str]
```

Add a partial unique index on `data_releases(status) WHERE status = 'active'`. Add a second partial expression index that permits at most one row whose status is `staging` or `validated`, preventing two refresh workspaces from being prepared concurrently. Add `data_release_id` to every release-bound spatial/derived table, change source uniqueness to include it, and add the subtype/proximity index on `(category_id, business_subtype, geom)` required by the spec.

- [ ] **Step 4: Write migration `0004` with safe v1 backfill**

The migration must create one `legacy-v1` active release, associate existing sources, backfill every existing row, add non-null constraints only after the backfill, expand the category check to the six migration-window slugs, and insert inactive `fnb`, `retail`, and `services` rows. Backfill legacy `business_subtype` from the current category slug and `taxonomy_version='v1.0.0'`.

- [ ] **Step 5: Apply the migration and run release tests**

Run:

```bash
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend pytest tests/integration/test_data_releases.py -q
```

Expected: migration succeeds against the current demo volume and all release tests pass.

- [ ] **Step 6: Commit the release foundation**

```bash
git add backend/alembic/versions/0004_data_releases_and_umbrella_categories.py backend/app/db/models.py backend/app/datasets/service.py backend/tests/integration/test_data_releases.py
git commit -m "feat: version GeoBiz data releases"
```

### Task 2: Build taxonomy v2 and subtype-aware staging

**Files:**
- Create: `backend/app/taxonomy/__init__.py`
- Create: `backend/app/taxonomy/businesses.py`
- Modify: `backend/app/imports/osm.py`
- Modify: `backend/app/imports/contracts.py`
- Modify: `backend/app/imports/quality.py`
- Test: `backend/tests/unit/test_business_taxonomy.py`
- Test: `backend/tests/unit/test_import_quality.py`

**Interfaces:**
- Consumes: OSM tag dictionaries.
- Produces: `TAXONOMY_VERSION`, `BusinessClassification`, `classify_business(tags)`, and staged `OsmBusinessRecord.business_subtype`.

- [ ] **Step 1: Write taxonomy tests for every allowed mapping group**

```python
@pytest.mark.parametrize(
    ("tags", "category", "subtype"),
    [
        ({"amenity": "restaurant"}, "fnb", "restaurant"),
        ({"shop": "bakery"}, "fnb", "bakery"),
        ({"shop": "supermarket"}, "retail", "supermarket"),
        ({"shop": "electronics"}, "retail", "electronics"),
        ({"leisure": "fitness_centre"}, "services", "fitness_centre"),
        ({"shop": "laundry"}, "services", "laundry"),
    ],
)
def test_classifies_supported_business(tags, category, subtype):
    assert classify_business(tags) == BusinessClassification(category, subtype)
```

Also test that pharmacy, clinic, school, office, hotel, generic `shop=yes`, and unknown tags return `None`.

- [ ] **Step 2: Pin ambiguous-tag behavior**

```python
def test_explicit_priority_resolves_supported_multi_match():
    result = classify_business({"amenity": "cafe", "shop": "bakery"})
    assert result == BusinessClassification("fnb", "cafe")


def test_cross_category_ambiguity_is_rejected():
    result = classify_business({"shop": "supermarket", "leisure": "fitness_centre"})
    assert result is None
```

- [ ] **Step 3: Run taxonomy tests and verify failure**

Run: `docker compose run --rm backend pytest tests/unit/test_business_taxonomy.py tests/unit/test_import_quality.py -q`

Expected: FAIL because the taxonomy package and subtype quality fields do not exist.

- [ ] **Step 4: Implement the explicit allow-list taxonomy**

Use immutable ordered rules:

```python
TAXONOMY_VERSION = "v2.0.0"

@dataclass(frozen=True)
class BusinessClassification:
    category_slug: Literal["fnb", "retail", "services"]
    subtype: str


def classify_business(tags: Mapping[str, str]) -> BusinessClassification | None:
    matches = [rule.classification for rule in BUSINESS_RULES if rule.matches(tags)]
    categories = {match.category_slug for match in matches}
    if len(categories) != 1:
        return None
    return matches[0]
```

List every subtype from spec section 4.1 explicitly; do not accept wildcard `shop` values.

- [ ] **Step 5: Extend staging and quality reports**

Add `business_subtype` and `taxonomy_version` to `OsmBusinessRecord`. Quality output must include umbrella category counts, subtype counts, ambiguous count, unsupported count, missing-name count, duplicates, invalid geometry, and outside-DKI count. Fail validation when an umbrella category is empty or an accepted record lacks subtype/version.

- [ ] **Step 6: Run taxonomy and existing import tests**

Run: `docker compose run --rm backend pytest tests/unit/test_business_taxonomy.py tests/unit/test_import_quality.py tests/unit/test_osm_import.py -q`

Expected: all tests pass and no v1 classification assertion remains.

- [ ] **Step 7: Commit taxonomy v2**

```bash
git add backend/app/taxonomy backend/app/imports backend/tests/unit
git commit -m "feat: classify umbrella business categories"
```

### Task 3: Make promotion and repositories release-isolated

**Files:**
- Create: `backend/app/releases/__init__.py`
- Create: `backend/app/releases/service.py`
- Modify: `backend/app/imports/promotion.py`
- Modify: `backend/app/analysis/repository.py`
- Modify: `backend/app/areas/service.py`
- Modify: `backend/app/analytics/service.py`
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/integration/test_release_isolation.py`

**Interfaces:**
- Consumes: `active_release_id(session)` from Task 1 and staged records from Task 2.
- Produces: `create_staging_release`, `activate_release`, `rollback_release`, `fail_release`, release-scoped promotion, and release-filtered runtime queries.

- [ ] **Step 1: Write a cross-release isolation test**

```python
def test_runtime_queries_only_read_active_release(db_session):
    old = seed_release(db_session, status="active", business_name="OLD BUSINESS")
    new = seed_release(db_session, status="validated", business_name="NEW BUSINESS")
    assert business_names(db_session) == ["OLD BUSINESS"]
    activate_release(db_session, new.id)
    assert business_names(db_session) == ["NEW BUSINESS"]
    assert old.status == "superseded"
```

Add equivalent assertions for POIs, roads, areas, normalization profiles, opportunity map, analytics, search, and dataset fingerprint.

- [ ] **Step 2: Run isolation tests and verify mixed rows**

Run: `docker compose run --rm backend pytest tests/integration/test_release_isolation.py -q`

Expected: FAIL because current queries have no release predicate and promotion deletes prior snapshots.

- [ ] **Step 3: Implement release lifecycle functions**

```python
def create_staging_release(session: Session, manifest: dict[str, Any]) -> DataRelease:
    release = DataRelease(
        release_key=manifest["release_key"],
        status="staging",
        dataset_fingerprint=manifest["dataset_fingerprint"],
        taxonomy_version="v2.0.0",
        scoring_version="v2.0.0",
        combined_manifest=manifest,
    )
    session.add(release)
    session.flush()
    return release


def activate_release(session: Session, release_id: int) -> None:
    session.execute(update(DataRelease).where(DataRelease.status == "active").values(status="superseded"))
    session.execute(update(DataRelease).where(DataRelease.id == release_id, DataRelease.status == "validated").values(status="active", activated_at=func.now()))
```

Require exactly one updated row for activation and reject staging/failed releases. Activation also toggles category activity from the release taxonomy version: v1 activates the three legacy categories; v2 activates only `fnb`, `retail`, and `services`. Implement `rollback_release(session, release_key)` by validating that the retained target is `superseded`, validating its tile artifact still exists, then passing its ID through the same activation path.

- [ ] **Step 4: Stop destructive snapshot replacement**

Promotion functions accept `release_id: int`, insert rows with that ID, and delete only rows belonging to the same non-active staging release during a retry. They never delete active or superseded release rows.

Dataset-source lookup uses `(slug, sha256)` and inserts a new immutable source row when the checksum changes. It never mutates checksum, observed date, retrieval date, URL, or licence on a source row already associated with a release.

- [ ] **Step 5: Add active-release predicates everywhere**

Resolve `release_id = active_release_id(session)` once per service call and include `table.data_release_id = :release_id` in every business, POI, road, transport, area, profile, score, analytics, search, and metadata query.

- [ ] **Step 6: Run release isolation and full backend tests**

Run:

```bash
docker compose run --rm backend pytest tests/integration/test_release_isolation.py -q
docker compose run --rm backend pytest -q
```

Expected: cross-release assertions and the complete suite pass.

- [ ] **Step 7: Commit release-scoped storage**

```bash
git add backend/app/releases backend/app/imports/promotion.py backend/app/analysis/repository.py backend/app/areas/service.py backend/app/analytics/service.py backend/app/api/routes.py backend/tests/integration/test_release_isolation.py
git commit -m "feat: isolate active data releases"
```

### Task 4: Add scoring v2 and detailed location evidence

**Files:**
- Create: `backend/alembic/versions/0005_seed_v2_scoring_weights.py`
- Modify: `backend/app/analysis/contracts.py`
- Modify: `backend/app/analysis/repository.py`
- Modify: `backend/app/analysis/service.py`
- Modify: `backend/app/scoring/service.py`
- Modify: `backend/app/scoring/generator.py`
- Modify: `backend/app/areas/generator.py`
- Test: `backend/tests/unit/test_scoring.py`
- Test: `backend/tests/integration/test_detailed_analysis.py`

**Interfaces:**
- Consumes: active release data and umbrella category slugs.
- Produces: extended `AnalyzeLocationResponse`, v2 normalization profiles, and 4,005 release-scoped opportunity scores.

- [ ] **Step 1: Write failing v2 weight tests**

Assert each category has the exact seven spec factors, its weights total `Decimal("1.0000")`, healthcare weight is zero, and a missing required factor returns `status="incomplete"` rather than zero substitution.

- [ ] **Step 2: Write detailed evidence integration tests**

```python
def test_analysis_returns_traceable_nearest_evidence(client, seeded_v2_release):
    response = client.post("/api/analyze-location", json={
        "latitude": -6.22691,
        "longitude": 106.80992,
        "business_category": "fnb",
        "radius_m": 1000,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["taxonomy_version"] == "v2.0.0"
    assert body["score"]["scoring_version"] == "v2.0.0"
    assert body["competitor_subtype_counts"]
    assert body["nearest_competitors"][0]["distance_m"] >= 0
    assert body["nearest_competitors"][0]["source_record_id"]
    assert "kecamatan" in body["containing_area"]
```

Also assert nearest items are distance-sorted, limited to ten, same-category only, and missing optional tags serialize as null.

- [ ] **Step 3: Run targeted tests and verify v2 is unavailable**

Run: `docker compose run --rm backend pytest tests/unit/test_scoring.py tests/integration/test_detailed_analysis.py -q`

Expected: FAIL on missing v2 weights and response fields.

- [ ] **Step 4: Seed exact v2 weights in migration `0005`**

Insert the table from spec section 6 for `fnb`, `retail`, and `services`; include a SQL assertion that every category total equals `1.0000`.

- [ ] **Step 5: Implement repository queries for detailed evidence**

Use `ST_DWithin(business.geom::geography, :point::geography, :radius_m)` for radius filters and `ST_Distance(business.geom::geography, :point::geography)` for ordered nearest evidence. Read subtype, address, brand, operator, hours, phone, and website from stored columns/tags without fallback invention. Extract `kecamatan` from active administrative-area properties.

- [ ] **Step 6: Extend contracts and analysis service**

Define typed models `NearbyBusiness`, `NearbyTransport`, `NearbyRoad`, `PoiBreakdown`, `AnalysisCoverage`, and the extended area context. Return source snapshot dates and both versions at the top level.

- [ ] **Step 7: Generate release-scoped profiles and scores**

Generators accept `release_id` and default versions to `v2.0.0`. They must create 15 profiles and exactly 4,005 opportunity rows for 267 areas × 3 categories × 5 radii.

- [ ] **Step 8: Run targeted and full backend tests**

Run:

```bash
docker compose run --rm backend pytest tests/unit/test_scoring.py tests/integration/test_detailed_analysis.py -q
docker compose run --rm backend pytest -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit scoring and evidence**

```bash
git add backend/alembic/versions/0005_seed_v2_scoring_weights.py backend/app/analysis backend/app/scoring backend/app/areas/generator.py backend/tests
git commit -m "feat: explain umbrella category scores"
```

### Task 5: Publish v2 API contracts and release status

**Files:**
- Modify: `backend/app/api/contracts.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/analytics/contracts.py`
- Modify: `backend/app/analytics/service.py`
- Create: `backend/app/releases/contracts.py`
- Test: `backend/tests/integration/test_v2_api.py`

**Interfaces:**
- Consumes: Tasks 1–4 release, taxonomy, analysis, and scoring services.
- Produces: v2 business/category APIs, `GET /api/map-config`, and `GET /api/refresh-status`.

- [ ] **Step 1: Write API contract tests**

Assert only `fnb`, `retail`, and `services` appear in categories; `restaurant`, `gym`, and `pharmacy` query values return 422; business GeoJSON includes subtype and available source attributes; analytics includes subtype composition; methodology includes taxonomy rules and v2 weights.

- [ ] **Step 2: Write release endpoint tests**

```python
def test_map_config_uses_active_release(client, active_release):
    response = client.get("/api/map-config")
    assert response.status_code == 200
    assert response.json()["release_id"] == active_release.id
    assert response.json()["tile_url"].endswith(active_release.tile_filename)


def test_refresh_status_is_read_only(client, active_release):
    response = client.get("/api/refresh-status")
    assert response.json()["active"]["release_key"] == active_release.release_key
    assert "trigger_url" not in response.json()
```

- [ ] **Step 3: Run API tests and verify failures**

Run: `docker compose run --rm backend pytest tests/integration/test_v2_api.py -q`

Expected: FAIL because v1 literals and missing endpoints remain.

- [ ] **Step 4: Implement strict v2 request/response types**

Create one `BusinessCategorySlug = Literal["fnb", "retail", "services"]` alias and import it across contracts. Remove hidden v1 category behavior. Map config returns release ID, local tile URL, SHA-256, DKI bounds, min/max zoom, attribution, mode, and online fallback availability.

- [ ] **Step 5: Extend analytics and methodology**

Analytics returns umbrella totals and subtype rows for the selected category. Methodology returns the complete taxonomy allow-list, taxonomy version, v2 scoring weights, release key, source snapshots, and limitations.

- [ ] **Step 6: Run API and full backend tests**

Run: `docker compose run --rm backend pytest tests/integration/test_v2_api.py -q && docker compose run --rm backend pytest -q`

Expected: all API contracts and existing tests pass after v1 expectations are intentionally updated.

- [ ] **Step 7: Commit API v2**

```bash
git add backend/app/api backend/app/analytics backend/app/releases/contracts.py backend/tests/integration/test_v2_api.py
git commit -m "feat: expose GeoBiz v2 release APIs"
```

### Task 6: Implement atomic on-demand refresh

**Files:**
- Create: `backend/app/refresh/__init__.py`
- Create: `backend/app/refresh/config.py`
- Create: `backend/app/refresh/downloader.py`
- Create: `backend/app/refresh/orchestrator.py`
- Create: `data/sources/geobiz-v2.json`
- Modify: `backend/app/imports/cli.py`
- Test: `backend/tests/unit/test_refresh_downloader.py`
- Test: `backend/tests/integration/test_refresh_orchestrator.py`

**Interfaces:**
- Consumes: release lifecycle, all staging/promotions, profile/score generators, and an already generated tile artifact from Task 7.
- Produces: `RefreshConfig`, `download_source`, `PreparedRelease`, the two exact orchestrator methods specified below, and CLI commands `refresh-prepare`, `refresh-activate`, `refresh-fail`, `refresh-status`, and `rollback-release`.

- [ ] **Step 1: Write downloader safety tests**

Cover allow-listed hosts, rejected cross-host redirects, connect/read timeout, maximum bytes, zero-byte response, streaming SHA-256, atomic temporary filename, HTTP 304 unchanged behavior, and removal of partial files after failure.

- [ ] **Step 2: Write two-phase orchestrator rollback tests**

```python
@pytest.mark.parametrize("failure_phase", ["download", "validate"])
def test_prepare_failure_keeps_old_release_active(db_session, old_release, failure_phase):
    orchestrator = build_orchestrator(fail_at=failure_phase)
    result = orchestrator.prepare(
        db_session,
        release_key="refresh-20261001-test",
        dry_run=False,
        accept_count_change=False,
    )
    assert result.status == "failed"
    assert active_release(db_session).id == old_release.id


@pytest.mark.parametrize("failure_phase", ["tile_verification", "derive"])
def test_activate_failure_keeps_old_release_active(db_session, old_release, prepared_release, failure_phase):
    orchestrator = build_orchestrator(fail_at=failure_phase)
    result = orchestrator.activate(
        db_session,
        release_key=prepared_release.release_key,
        tile_path=prepared_release.expected_tile_path,
    )
    assert result.status == "failed"
    assert active_release(db_session).id == old_release.id
```

Also test advisory-lock contention in each phase, rejection of a second `staging`/`validated` release, activation of anything except a `validated` release, no-op unchanged inputs, dry-run creates no release, and count-change thresholds require `--accept-count-change`.

- [ ] **Step 3: Run refresh tests and verify failure**

Run: `docker compose run --rm backend pytest tests/unit/test_refresh_downloader.py tests/integration/test_refresh_orchestrator.py -q`

Expected: FAIL because refresh modules do not exist.

- [ ] **Step 4: Add committed source configuration**

`data/sources/geobiz-v2.json` contains exact URLs, hosts, licences, filenames, byte limits, and population period. OSM roles share the same Jakarta PBF definition. Population remains the verified 2025 configuration until the file is explicitly changed.

- [ ] **Step 5: Implement safe streaming downloads**

Use Python standard-library `urllib.request` with explicit timeout and a custom redirect handler that validates destination hosts. Stream in 1 MiB chunks, enforce configured size limits, calculate SHA-256, `fsync`, and atomically rename completed downloads.

- [ ] **Step 6: Implement the preparation phase**

Implement the exact public signature `prepare(self, session: Session, *, release_key: str, dry_run: bool, accept_count_change: bool) -> PreparedRelease`.

It performs preflight checks for database connectivity, writable workspace/tile directories, configured sources, and documented minimum free disk space. It then acquires `pg_try_advisory_lock(hashtext('geobiz-refresh'))`, rejects an existing `staging` or `validated` release, creates an isolated persistent release workspace, downloads sources, writes the checksum manifest, stages records, and runs source/count/geometry/taxonomy validation. The manifest keeps publisher observation time separate from retrieval time. A real preparation promotes the validated base rows into release-bound tables while they remain invisible to runtime queries, then persists a `validated` release whose manifest includes the verified PBF path, boundary path, expected immutable tile path, and workspace path. A dry run performs the same source validation in a temporary workspace but creates no release or database rows. If every checksum matches the active release, return `status="unchanged"` without creating a release. Any exception records a failed release in a separate short transaction and always releases the phase lock.

- [ ] **Step 7: Implement the activation phase**

Implement the exact public signature `activate(self, session: Session, *, release_key: str, tile_path: Path) -> DataRelease`.

It acquires the same advisory lock, accepts only the single `validated` release, verifies that the tile path is the release's expected immutable path, and delegates PMTiles header/checksum validation to Task 7. In one database transaction it attaches the tile metadata, derives profiles and scores from the prepared release-bound base rows, validates exactly 4,005 opportunity scores, supersedes the old release, and activates the new release. Any failure rolls the transaction back, marks the prepared release failed in a separate short transaction, leaves the old release active, and releases the phase lock. Neither phase invokes Docker or holds a database advisory lock while an external container runs.

- [ ] **Step 8: Add phase CLIs**

`refresh-prepare --release-key <key> [--dry-run] [--accept-count-change]` prints one JSON object containing the release key, status, workspace, verified PBF path, boundary path, and expected tile path. `refresh-activate --release-key <key> --tile <path>` prints the activated release. `refresh-fail --release-key <key> --phase <phase> --message <message>` idempotently marks an incomplete prepared release failed so the host wrapper can clean up after tilemaker errors. `verify-tile-service --release-key <key>` checks Martin's catalog and representative DKI tiles. Keep read-only `refresh-status` and add `rollback-release <release-key>`; rollback requires the retained immediately previous release and a healthy tile artifact. Never enable count-change acceptance by default.

- [ ] **Step 9: Run refresh tests**

Run: `docker compose run --rm backend pytest tests/unit/test_refresh_downloader.py tests/integration/test_refresh_orchestrator.py -q`

Expected: all tests pass without using the public network.

- [ ] **Step 10: Commit refresh pipeline**

```bash
git add backend/app/refresh backend/app/imports/cli.py backend/tests data/sources/geobiz-v2.json
git commit -m "feat: refresh GeoBiz data on demand"
```

### Task 7: Generate and serve the offline DKI basemap

**Files:**
- Create: `data/tiles/.gitkeep`
- Create: `data/tiles/config/geobiz.json`
- Create: `data/tiles/config/geobiz.lua`
- Create: `data/tiles/martin.yaml`
- Create: `backend/app/refresh/tiles.py`
- Create: `scripts/refresh-data.sh`
- Create: `scripts/prepare-offline-map.sh`
- Modify: `backend/app/imports/cli.py`
- Modify: `.gitignore`
- Modify: `compose.yaml`
- Modify: `.env.example`
- Modify: `Makefile`
- Test: `backend/tests/unit/test_tile_release.py`

**Interfaces:**
- Consumes: prepared-release JSON, verified Jakarta PBF, DKI boundary, and release key.
- Produces: `TileArtifact(filename: str, sha256: str, byte_size: int)`, `verify_pmtiles(path: Path, release_key: str) -> TileArtifact`, one-command host orchestration, and local tile service at `http://tiles:3000` / host port 3000.

- [ ] **Step 1: Write tile artifact tests**

Assert local artifact verification accepts only immutable `<release-key>.pmtiles`, verifies the PMTiles header, non-zero bytes, SHA-256, and release-key/path agreement. Add a mocked HTTP test for the separate Martin catalog/representative-tile check. Reject release keys outside `[a-z0-9-]+` and reject `.partial` artifacts.

- [ ] **Step 2: Run tile tests and verify missing implementation**

Run: `docker compose run --rm backend pytest tests/unit/test_tile_release.py -q`

Expected: FAIL because `refresh.tiles` is missing.

- [ ] **Step 3: Add pinned tile services**

Add Compose services:

```yaml
  tiles:
    image: ghcr.io/maplibre/martin:v1.16.1
    command: ["--config", "/config/martin.yaml"]
    volumes:
      - ./data/tiles:/tiles:ro
      - ./data/tiles/martin.yaml:/config/martin.yaml:ro
    ports:
      - "3000:3000"

  tilemaker:
    image: ghcr.io/systemed/tilemaker:v3.2.0
    profiles: ["tools"]
    volumes:
      - ./data:/data
```

- [ ] **Step 4: Add explicit tilemaker schema**

Configure DKI bounds and layers `water`, `waterway`, `landuse`, `building`, `transportation`, `boundary`, `place`, and `poi`. Lua must copy only style-required attributes such as `class`, `subclass`, `name`, `ref`, and `admin_level`; it must not copy all source tags into tiles.

- [ ] **Step 5: Implement tile verification**

`verify_pmtiles` reads the generated artifact but never launches Docker or tilemaker. Validate the PMTiles header and checksum locally, verify the filename matches the release key, and return `TileArtifact`. Implement a separate `verify_tile_service(base_url, release_key)` helper for Martin catalog and representative z/x/y checks. `refresh-activate` refuses to attach a tile when the prepared release's OSM checksum differs from its recorded source checksum.

- [ ] **Step 6: Implement one-command host orchestration**

`scripts/refresh-data.sh` uses `set -Eeuo pipefail`, creates a collision-resistant lowercase release key (`refresh-<UTC timestamp>-<pid>`), and calls the following phases in order:

1. `docker compose run --rm backend python -m app.imports.cli refresh-prepare --release-key "$release_key"`; all workspace paths are deterministic under `/data/refresh/$release_key`, so the script does not need to parse log text.
2. `docker compose run --rm tilemaker` with an explicit argument array to build `<release-key>.pmtiles.partial` from `/data/refresh/$release_key/sources/jakarta.osm.pbf` and its verified boundary.
3. Atomically rename the completed tile to `<release-key>.pmtiles`, start `tiles`, and validate its catalog plus representative tiles.
4. `docker compose run --rm backend python -m app.imports.cli refresh-activate --release-key "$release_key" --tile "/data/tiles/releases/$release_key.pmtiles"`.

An `ERR` trap removes only the current `.partial` artifact and invokes idempotent `refresh-fail` for the current release; it never deletes an active/superseded artifact. Forward `--accept-count-change` only when the operator supplied it.

`scripts/prepare-offline-map.sh` first calls `offline-map-prepare --release-key <key>`. That command clones the current release's immutable source associations and release-bound base/derived rows into a new `validated` successor with the same taxonomy, scoring version, and dataset fingerprint, but an expected new tile path; it refuses to proceed unless the manifest points to a verified PBF whose checksum matches the active release. The script builds and verifies the PMTiles artifact, then uses the normal `refresh-activate` path so the original active release is never mutated. If the active release already records an artifact and only its local file is missing/corrupt, the script may reconstruct that exact filename but must require the checksum to match before replacement. Normal data updates always use `refresh-data.sh`.

- [ ] **Step 7: Add Make targets and ignore rules**

```make
refresh-data:
	./scripts/refresh-data.sh $(if $(filter 1 true yes,$(ACCEPT_COUNT_CHANGE)),--accept-count-change,)

refresh-data-dry-run:
	docker compose run --rm backend python -m app.imports.cli refresh-prepare --release-key dry-run --dry-run

refresh-status:
	docker compose run --rm backend python -m app.imports.cli refresh-status

prepare-offline-map:
	./scripts/prepare-offline-map.sh
```

Add `rollback-release` with an explicit non-empty `RELEASE` guard before invoking the backend CLI. The script and CLI contract must not parse human-formatted log lines; the preparation command's stdout is JSON and diagnostics go to stderr.

Ignore `data/tiles/releases/*.pmtiles`, `.partial`, and tilemaker temporary storage while retaining configuration and `.gitkeep`.

- [ ] **Step 8: Run tests and a real current-snapshot tile build**

Run:

```bash
docker compose run --rm backend pytest tests/unit/test_tile_release.py -q
make refresh-data
docker compose up -d tiles
curl -fsS http://localhost:3000/catalog
```

Expected: unit tests pass, an ignored PMTiles artifact exists, and Martin lists it.

- [ ] **Step 9: Commit offline tile infrastructure**

```bash
git add .gitignore .env.example compose.yaml Makefile scripts data/tiles backend/app/refresh/tiles.py backend/app/imports/cli.py backend/tests/unit/test_tile_release.py
git commit -m "feat: serve an offline DKI basemap"
```

### Task 8: Upgrade the frontend to v2 and local maps

**Files:**
- Create: `frontend/src/map/localStyle.ts`
- Create: `frontend/src/components/NearbyEvidence.tsx`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/components/GeoMap.tsx`
- Modify: `frontend/src/styles/index.css`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/src/app/App.test.tsx`
- Create: `frontend/src/components/NearbyEvidence.test.tsx`

**Interfaces:**
- Consumes: v2 API and `/api/map-config` from Task 5.
- Produces: v2 category UI, subtype popups, detailed evidence panels, PMTiles-backed map, and explicit offline/fallback states.

- [ ] **Step 1: Install pinned PMTiles client**

Run: `docker compose run --rm frontend npm install --save-exact pmtiles@4.5.0`

Expected: package and lockfile pin exactly `4.5.0`.

- [ ] **Step 2: Write failing frontend contract tests**

Update fetch mocks to expose `fnb`, `retail`, and `services`. Assert the old category labels are absent, detail cards render subtype mix/nearest evidence, and unavailable optional source tags show `Not mapped` rather than invented content. Start the v2 frontend against a mocked active `v1.0.0` release and assert an explicit upgrade-required state instead of mismatched category controls.

- [ ] **Step 3: Write map config tests**

Mock an offline config and assert the map style has no `http://` or `https://` source other than the configured local tile origin. Mock a missing tile config and assert the “Online fallback” badge and retry control render without clearing an existing score.

- [ ] **Step 4: Run tests and verify v1 contract failures**

Run: `docker compose run --rm frontend npm test -- --run`

Expected: FAIL on old category types and missing evidence/map config components.

- [ ] **Step 5: Replace frontend domain types**

Set `BusinessCategory = "fnb" | "retail" | "services"`. Add typed `BusinessSubtypeCount`, `NearbyBusiness`, `NearbyTransport`, `NearbyRoad`, `AnalysisCoverage`, and `MapConfig`. Delete all restaurant/gym/pharmacy label branches.

Change the browser API base to same-origin `/api`. Configure Vite proxies `/api` → `http://backend:8000` and `/tiles` → `http://tiles:3000`, preserving Range headers. Map config returns a relative `/tiles/releases/<release-key>.pmtiles` URL so host browsers and the E2E container use the same contract without container-specific public hostnames.

- [ ] **Step 6: Register PMTiles and construct the local style**

```ts
const protocol = new Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

export function localStyle(config: MapConfig): StyleSpecification {
  return {
    version: 8,
    sources: { geobiz: { type: "vector", url: `pmtiles://${config.tile_url}` } },
    layers: buildLocalLayers(),
  };
}
```

Do not set remote `glyphs` or `sprite` URLs. Keep OSM attribution visible.

- [ ] **Step 7: Implement v2 UI and evidence**

Update selectors, colors, rankings, analytics links, popup content, and search labels. Add subtype composition bars, nearest competitor list with metre/kilometre formatting, nearest transit/road, kecamatan, population period, and coverage. Preserve selected location/layers across category changes. Gate the application on release taxonomy compatibility and render the tested upgrade-required state whenever the API still exposes v1.

- [ ] **Step 8: Handle offline/fallback state**

Fetch map config before map construction. Default to local tiles when available; use OpenFreeMap only when `fallback_available` is true and show the badge. Retry only map setup and preserve React analysis state.

- [ ] **Step 9: Run frontend tests, lint, and build**

Run:

```bash
docker compose run --rm frontend npm test -- --run
docker compose run --rm frontend npm run lint
docker compose run --rm frontend npm run build
```

Expected: all tests pass and production build succeeds.

- [ ] **Step 10: Commit frontend v2**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src
git commit -m "feat: present umbrella business evidence"
```

### Task 9: Complete v2 analytics and methodology presentation

**Files:**
- Modify: `frontend/src/components/AnalyticsView.tsx`
- Modify: `frontend/src/components/MethodologyView.tsx`
- Modify: `frontend/src/components/ProductViews.test.tsx`
- Modify: `frontend/src/styles/index.css`

**Interfaces:**
- Consumes: extended analytics/methodology contracts from Task 5.
- Produces: subtype composition analytics and auditable taxonomy/release methodology.

- [ ] **Step 1: Write failing product-view tests**

Assert Analytics shows all three umbrella totals, subtype composition for the selected category, 267-area score distribution, release key, and no revenue metric. Assert Methodology shows taxonomy v2 mappings, exact v2 weights, PMTiles checksum, source dates/licences, dataset fingerprint, and all interpretation limits.

- [ ] **Step 2: Run focused tests and verify missing sections**

Run: `docker compose run --rm frontend npm test -- --run src/components/ProductViews.test.tsx`

Expected: FAIL on subtype/taxonomy/release content.

- [ ] **Step 3: Implement analytics and methodology sections**

Reuse API-provided definitions; do not duplicate taxonomy or weights in UI constants. Render long subtype/source lists with accessible tables, empty states, wrapping identifiers, and tabular numerals.

- [ ] **Step 4: Run frontend verification**

Run: `docker compose run --rm frontend npm test -- --run && docker compose run --rm frontend npm run build`

Expected: all tests and build pass.

- [ ] **Step 5: Commit analytics/methodology v2**

```bash
git add frontend/src/components frontend/src/styles/index.css
git commit -m "feat: document v2 taxonomy and coverage"
```

### Task 10: Add live Docker Playwright E2E

**Files:**
- Create: `e2e/package.json`
- Create: `e2e/package-lock.json`
- Create: `e2e/playwright.config.ts`
- Create: `e2e/tests/map-explorer.spec.ts`
- Create: `e2e/tests/analytics-methodology.spec.ts`
- Create: `e2e/tests/offline.spec.ts`
- Create: `e2e/tests/recovery.spec.ts`
- Modify: `compose.yaml`
- Modify: `Makefile`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: complete live v2 stack and active offline tile release.
- Produces: `make e2e` and failure-only traces/screenshots.

- [ ] **Step 1: Create pinned E2E package**

`e2e/package.json` pins `@playwright/test` to `1.63.0`. Configure Chromium only, `baseURL=http://frontend:5173`, one worker, trace/screenshot on first retry, and no automatic local web server.

- [ ] **Step 2: Add the Playwright Compose service**

```yaml
  e2e:
    image: mcr.microsoft.com/playwright:v1.63.0-noble
    working_dir: /e2e
    volumes:
      - ./e2e:/e2e
    environment:
      BASE_URL: http://frontend:5173
    depends_on:
      - frontend
      - backend
      - tiles
```

- [ ] **Step 3: Write the complete user-journey test**

Use roles/labels to switch all three categories, search and select SENAYAN, wait for the score request, change radius, toggle every layer, inspect a real business popup, apply opportunity filters, and pin exactly three areas. Assert the fourth compare checkbox is disabled.

- [ ] **Step 4: Write Analytics and Methodology tests**

Navigate by links and assert category totals, subtype composition, 267-area evidence, taxonomy version, scoring version, source attribution, licence, fingerprint, release key, and limitations.

- [ ] **Step 5: Write the offline test**

```ts
test("renders the complete local map without internet", async ({ page }) => {
  await page.route("**/*", async route => {
    const host = new URL(route.request().url()).hostname;
    if (host === "frontend") await route.continue();
    else await route.abort("blockedbyclient");
  });
  await page.goto("/");
  await expect(page.getByLabel("Peta interaktif bisnis DKI Jakarta")).toBeVisible();
  await expect(page.getByText("Offline map")).toBeVisible();
  await expect(page.getByText("Location score")).toBeVisible();
});
```

- [ ] **Step 6: Write recovery tests**

Route the analyze endpoint to 503 and assert Retry analysis; allow the next request and assert score recovery. Route local tiles to failure and assert Retry map plus preserved score text.

- [ ] **Step 7: Add Make target and ignore artifacts**

```make
e2e:
	docker compose run --rm e2e npm ci
	docker compose run --rm e2e npx playwright test
```

Ignore `e2e/test-results/`, `e2e/playwright-report/`, and blob reports.

- [ ] **Step 8: Run E2E twice**

Run: `make e2e && make e2e`

Expected: both runs pass without order dependence and the offline project makes zero successful external requests.

- [ ] **Step 9: Commit browser E2E**

```bash
git add e2e compose.yaml Makefile .gitignore
git commit -m "test: cover GeoBiz live browser journeys"
```

### Task 11: Validate refresh, rollback, and documentation

**Files:**
- Modify: `README.md`
- Modify: `data/README.md`
- Modify: `docs/demo-runbook.md`
- Create: `docs/data-refresh-runbook.md`
- Modify: `backend/tests/integration/test_demo_data_integrity.py`

**Interfaces:**
- Consumes: every prior task.
- Produces: reproducible operator documentation and final acceptance evidence.

- [ ] **Step 1: Update real-demo integrity assertions**

Replace exact v1 counts with v2 invariants: all three categories non-empty, every business has subtype/version/source identity, no prohibited provider, valid DKI geometry, exactly 267 populated areas, exactly 15 profile scopes, and exactly 4,005 opportunity scores for the active release. Record actual category/subtype counts in test output rather than asserting invented targets.

- [ ] **Step 2: Run a dry refresh and inspect status**

Run:

```bash
make refresh-data-dry-run
make refresh-status
```

Expected: dry run reports source changes and quality counts but active release ID remains unchanged.

- [ ] **Step 3: Run a real refresh and validate release activation**

Run `make refresh-data`. If category/supporting-data count warnings cross the documented threshold, inspect the quality report and rerun with `make refresh-data ACCEPT_COUNT_CHANGE=1` only when the changes match the broadened taxonomy.

Expected: new v2 release becomes active, PMTiles checksum is recorded, and previous release remains superseded and retained.

- [ ] **Step 4: Exercise rollback**

Run `make rollback-release RELEASE=<previous-release-key>`, verify API category/data fingerprint and tile URL switch together, then run `make rollback-release RELEASE=<v2-release-key>` to reactivate v2. Document exact commands and outputs in the refresh runbook.

- [ ] **Step 5: Update documentation**

Document initial setup, source configuration, dry-run, refresh, count-change approval, tile preparation, status, rollback, offline demo, E2E, disk use, retained releases, limitations, and zero-billing statement. Retain the active release, the immediate rollback release, and at most one older superseded release by default; pruning must never remove an active/referenced artifact. Explicitly state population remains pinned until configured with a verified newer official period.

- [ ] **Step 6: Run the final acceptance suite**

Run:

```bash
docker compose config --quiet
docker compose run --rm backend pytest -q
docker compose run --rm frontend npm test -- --run
docker compose run --rm frontend npm run lint
docker compose run --rm frontend npm run build
make e2e
```

Expected: all commands pass. Only known third-party deprecation warnings may remain; no failed, skipped critical, or flaky tests are accepted.

- [ ] **Step 7: Audit repository contents**

Run:

```bash
git status --short
git check-ignore data/raw/jakarta.osm.pbf data/tiles/releases/*.pmtiles
git diff --check
```

Expected: raw and tile artifacts are ignored, the user-owned PRD remains untracked unless the user explicitly adds it, and no whitespace errors exist.

- [ ] **Step 8: Commit final documentation and verification**

```bash
git add README.md data/README.md docs backend/tests/integration/test_demo_data_integrity.py
git commit -m "docs: operate GeoBiz v2 data releases"
```

- [ ] **Step 9: Review and push**

Review the complete branch diff against the spec, fix any P1/P2 finding, rerun affected tests, verify commit authorship is the configured user, then push the completed commits to `origin/main` only after the user-authorized execution workflow reaches completion.
