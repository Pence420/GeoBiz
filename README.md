# GeoBiz

GeoBiz is a DKI Jakarta business-location intelligence dashboard for restaurants,
gyms, and pharmacies. It combines traceable public datasets with transparent,
versioned scoring. Demo records are real businesses from OpenStreetMap; synthetic
data is restricted to tests.

## Local development

```bash
cp .env.example .env
docker compose up --build
docker compose run --rm backend alembic upgrade head
```

- Dashboard: <http://localhost:5173>
- API docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/api/health>

The map uses MapLibre GL JS with the free OpenFreeMap public style. It requires
no account, API key, or billing setup. Map attribution remains visible in the UI.

## Verification

```bash
docker compose run --rm backend pytest -q
docker compose run --rm frontend npm test -- --run
docker compose run --rm frontend npm run build
```

See [`data/README.md`](data/README.md) for source manifests, quality gates, and
reproducible import commands.
