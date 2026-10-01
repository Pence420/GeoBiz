# GeoBiz

GeoBiz is a DKI Jakarta business-location intelligence dashboard for restaurants,
gyms, and pharmacies. It combines traceable public datasets with transparent,
versioned scoring. Demo records are real businesses from OpenStreetMap; synthetic
data is restricted to tests.

The completed MVP includes:

- interactive MapLibre map with business clusters, heatmap, population and
  opportunity choropleths, transit, commercial, education, office, and road layers;
- local search for DKI areas, businesses, landmarks, and coordinates;
- click-to-analyze buffers at 500 m, 1 km, 2 km, 3 km, and 5 km;
- category-specific 0–100 scoring, factor breakdowns, rankings, filters, and
  three-area comparison;
- aggregate analytics and a methodology/provenance view backed by the same
  versioned database snapshot;
- Docker-only setup with no paid API, account, API key, or billing dependency.

## Local development

```bash
cp .env.example .env
docker compose up --build
docker compose run --rm backend alembic upgrade head
```

The checked-in source manifests describe how to reproduce the real dataset. If
the database has not been populated yet, follow [`data/README.md`](data/README.md),
then generate the versioned profiles and opportunity observations:

```bash
make profiles
make opportunities
```

- Dashboard: <http://localhost:5173>
- API docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/api/health>

The map uses MapLibre GL JS with the free OpenFreeMap public style. It requires
no account, API key, or billing setup. Map attribution remains visible in the UI.

## Verification

```bash
make test
make build-frontend
make lint
```

See [`data/README.md`](data/README.md) for source manifests, quality gates, and
reproducible import commands. See [`docs/demo-runbook.md`](docs/demo-runbook.md)
for the academic demo flow, integrity checks, and troubleshooting.
