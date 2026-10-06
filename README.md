# GeoBiz

GeoBiz is a DKI Jakarta business-location intelligence dashboard for the umbrella
categories **F&B**, **Retail**, and **Services**. It combines traceable public
datasets with transparent, versioned scoring. Demo records are real businesses
from OpenStreetMap; synthetic data is restricted to isolated automated tests.

The v2 application includes:

- an offline-first MapLibre map served from a release-scoped local PMTiles archive;
- local search, real business popups, clusters, heatmap, population, opportunity,
  transit, commercial, education, office, and road layers;
- click-to-analyze buffers at 500 m, 1 km, 2 km, 3 km, and 5 km;
- category-specific 0–100 scoring, nearby subtype evidence, rankings, filters,
  and three-area comparison;
- analytics and methodology views tied to the same release fingerprint;
- on-demand, checksum-verified refreshes with atomic activation and rollback;
- Docker-only operation with no paid API, account, API key, or billing dependency.

## Start locally

```bash
cp .env.example .env
docker compose up -d --build
make migrate
```

If the database is empty, prepare and activate a release from the configured
public sources:

```bash
make refresh-data-dry-run
make refresh-data
```

The full refresh downloads into an isolated workspace, validates the sources,
builds a local DKI PMTiles archive, verifies representative tiles, derives all
15 category/radius scoring scopes, and only then changes the active release.
See [`data/README.md`](data/README.md) for source details and the retained-snapshot
workflow, and [`docs/data-refresh-runbook.md`](docs/data-refresh-runbook.md) for
operations and rollback.

- Dashboard: <http://localhost:5173>
- API docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/api/health>
- Tile service: <http://localhost:3000>

## Run the same demo on another laptop

A Git clone contains application code and source manifests, but not the populated
PostgreSQL volume, raw source snapshots, or PMTiles archives. To show the **same
verified release and real businesses** on another laptop, transfer a database
dump and the local data files together. Use the same Git commit on both laptops.
The commands below use a macOS/Linux shell (or WSL on Windows) and a fresh
GeoBiz database on the receiving laptop. Docker must have internet access once
to pull images and build the app; the running demo then uses the local map.

On the laptop that already has the working demo, start Docker/Colima and GeoBiz,
then run these commands from the repository root:

```bash
docker compose up -d db
mkdir -p ../geobiz-demo-transfer
docker compose exec -T db pg_dump -U geobiz -d geobiz -Fc \
  > ../geobiz-demo-transfer/geobiz.dump
tar -czf ../geobiz-demo-transfer/geobiz-data.tar.gz \
  data/raw data/tiles/releases
git rev-parse HEAD
```

Copy the `geobiz-demo-transfer` folder to the other laptop and note the printed
commit. `geobiz.dump` contains the release-scoped business, area, and score
records; the archive contains the matching raw sources and offline map files.
Keep this transfer folder outside the Git repository and do not publish the dump.

On the receiving laptop, install Docker Desktop (or Docker Engine with Compose),
copy `geobiz-demo-transfer` next to where you will clone the project, and run:

```bash
git clone https://github.com/Pence420/GeoBiz.git
cd GeoBiz
git checkout COMMIT_SHA_FROM_EXPORT
cp .env.example .env
tar -xzf ../geobiz-demo-transfer/geobiz-data.tar.gz -C .
docker compose up -d db
docker compose exec -T db pg_restore -U geobiz -d geobiz \
  --no-owner --no-acl --exit-on-error \
  < ../geobiz-demo-transfer/geobiz.dump
docker compose up -d --build backend tiles frontend
curl -fsS http://localhost:8000/api/map-config
```

Open <http://localhost:5173>. The map-config response should show an active v2
release with `mode: "offline"` and a `tile_url` whose PMTiles file exists under
`data/tiles/releases/`. Do not run `make migrate` or `make refresh-data` when
restoring this same-version dump: it already contains the schema and verified
release. Replace `COMMIT_SHA_FROM_EXPORT` with the hash printed by `git rev-parse
HEAD` on the source laptop. The transfer needs enough free disk space for the
archive, restored files, database, and Docker images. If the receiving laptop
has an existing GeoBiz database, back it up first and restore into a fresh
Compose volume instead of merging datasets.

For a new dataset rather than an identical demo, follow the regular setup above
and run `make refresh-data`; this downloads and validates current public sources,
so its records and availability can differ from the transferred snapshot.

## Verify

```bash
docker compose config --quiet
make test
make lint
make build-frontend
make e2e
```

`make e2e` runs Chromium against the live Docker stack, including a mode that
blocks every non-local browser request. Failure traces and screenshots stay
under ignored `e2e/` report directories.

## Cost and data policy

GeoBiz uses PostgreSQL/PostGIS, FastAPI, React, MapLibre GL JS, PMTiles,
Martin, and tilemaker. The default map and analysis path is local after a
release is prepared. The optional online fallback is not required for the
offline demo. There is no Google Maps integration, subscription service,
payment flow, or billing configuration.

Raw PBF, GTFS, population, refresh workspaces, and PMTiles archives are ignored
because they are large. Committed manifests/configuration retain source URLs,
licences, retrieval metadata, and checksums. Never add invented business names,
coordinates, counts, or promoted synthetic fixtures.

See [`docs/demo-runbook.md`](docs/demo-runbook.md) for the presentation flow and
verified demo invariants.
