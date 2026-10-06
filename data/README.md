# GeoBiz data workspace

GeoBiz promotes only traceable real-world data. Large raw and generated files
are ignored by Git; committed manifests and `data/sources/geobiz-v2.json` make
their origin and validation rules reviewable.

## v2 sources

| Role | Provider | Use |
| --- | --- | --- |
| OSM extract | OpenStreetMap / download.openstreetmap.fr | F&B, Retail, Services, contextual POIs, roads, and vector basemap |
| DKI boundary | OpenStreetMap via Nominatim | geographic clipping and coverage validation |
| GTFS | PT Transportasi Jakarta | TransJakarta stops |
| Population | Satu Data Jakarta / Dukcapil DKI | kelurahan population, density, and age/gender cohorts |

OpenStreetMap remains attributed as `© OpenStreetMap contributors` under ODbL.
The population snapshot is pinned to the verified 2025 period until a newer
official period is configured, downloaded, and checksum-validated. A source
endpoint changing method, schema, or period must fail the refresh; it must not
silently reuse or invent rows.
New releases retain validated age/gender cohorts alongside each population
area. Older releases read the local raw snapshot only when its checksum matches
the population source linked to that release; missing or mismatched snapshots
show incomplete coverage instead of fabricated figures.

Rules:

- Never add invented businesses, names, coordinates, or competitor counts.
- Raw downloads go under `data/raw/`; isolated runs go under `data/refresh/`.
- PMTiles archives go under `data/tiles/releases/` and are immutable per release.
- Every promoted row retains release, source, and source-record identity.
- Synthetic fixtures stay under `backend/tests/fixtures/` and are never promoted.

## Online refresh

```bash
make refresh-data-dry-run
make refresh-status
make refresh-data
```

The dry run downloads and validates in an isolated temporary workspace without
creating or activating a release. The full run creates a unique release key,
builds PMTiles from that release's verified PBF, checks the tile catalog and
representative DKI tiles, derives profiles/opportunities, and activates in one
database transaction.

Counts are compared with the active release. A decrease over 30% or increase
over 100% in an umbrella category or primary supporting dataset stops the run.
After reviewing the quality output and confirming a legitimate source/taxonomy
change, explicitly approve it with:

```bash
make refresh-data ACCEPT_COUNT_CHANGE=1
```

## Prepare from retained verified snapshots

This network-free preparation path is useful for the academic demo when the
official endpoint is temporarily unavailable. It verifies every raw file against
its committed manifest before staging; it does not bypass data quality gates.

```bash
docker compose run --rm backend python -m app.imports.cli refresh-prepare-local \
  --release-key demo-v2-YYYYMMDD \
  --osm /data/raw/jakarta.osm.pbf \
  --osm-manifest /data/manifests/osm-dki-businesses-2026-09-29.json \
  --boundary /data/raw/dki-boundary.geojson \
  --boundary-manifest /data/manifests/osm-dki-boundary-2026-09-29.json \
  --gtfs /data/raw/transjakarta-gtfs.zip \
  --gtfs-manifest /data/manifests/transjakarta-gtfs-2026-07-24.json \
  --population /data/raw/dki-population-2025.json \
  --population-manifest /data/manifests/satudata-dki-population-2025.json
```

The command prints the exact PBF input and expected PMTiles output. Build the
tile with the pinned tilemaker service, verify it with `verify-tile-service`,
then activate with `refresh-activate`. The complete safe sequence is documented
in [`../docs/data-refresh-runbook.md`](../docs/data-refresh-runbook.md).

## Quality invariants

A v2 release cannot activate unless:

- F&B, Retail, and Services are all non-empty;
- every business has subtype, taxonomy version, source type/ID, and valid DKI geometry;
- duplicate source identities and prohibited synthetic providers are zero;
- exactly 267 kelurahan have population density;
- exactly 15 normalization scopes and 4,005 opportunity observations exist;
- scoring weights total 1.0 per category;
- the PMTiles checksum is recorded and representative tiles are readable.

The current verified snapshot reports 3,415 F&B, 2,145 Retail, and 774 Services
records. These are evidence printed by the integrity test, not hard-coded future
targets: legitimate public-source updates may change them after passing the gates.

## Storage and retention

A local v2 run needs at least 2 GB free before preparation. Tilemaker can use
several GB temporarily under `data/tiles/tmp/`; PMTiles and PBF artifacts are
typically tens to hundreds of MB. Keep the active release, its immediate rollback
release, and at most one older superseded release by default. Never prune an
active release, the immediate rollback target, or any referenced tile/PBF. Review
`make refresh-status` and database references before manual cleanup.
