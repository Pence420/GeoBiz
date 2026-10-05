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
