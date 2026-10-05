# GeoBiz academic demo runbook

This runbook presents and verifies GeoBiz v2 for DKI Jakarta without a paid
service. Docker must be running and ports 5173, 8000, 3000, and 5432 available.

## 1. Start and check the stack

```bash
cp .env.example .env
docker compose up -d --build
make migrate
make refresh-status
```

Open <http://localhost:5173>. The API documentation is at
<http://localhost:8000/docs> and the health endpoint at
<http://localhost:8000/api/health>. The active status must show taxonomy and
scoring `v2.0.0`, a dataset fingerprint, tile filename, and tile SHA-256.

If no v2 release is active, follow [`data-refresh-runbook.md`](data-refresh-runbook.md).

## 2. Verify before presenting

```bash
docker compose config --quiet
docker compose run --rm backend pytest -q
docker compose run --rm frontend npm test -- --run
docker compose run --rm frontend npm run lint
docker compose run --rm frontend npm run build
make e2e
```

The integrity suite requires three non-empty umbrella categories, complete
source/taxonomy/subtype identity, valid DKI geometry, no synthetic provider,
267 populated kelurahan, 15 profiles, and 4,005 opportunity scores. Actual
category/subtype counts are printed as evidence rather than frozen as invented
targets. Browser E2E uses the live promoted database and includes a zero-external-
request offline scenario.

## 3. Presentation flow

1. Open **Map explorer** and point out the **Offline map** badge and OSM attribution.
2. Switch among **F&B**, **Retail**, and **Services**.
3. Search **SENAYAN**, then inspect a real business from the map/table popup; show
   its OSM element type and record ID.
4. Change radius and toggle opportunity, competitors, heatmap, population,
   transit, commercial, education, offices, and road network.
5. Explain the location score, factor weights, nearby subtype mix, closest named
   evidence, missing-data handling, and dataset fingerprint.
6. Filter ranked kelurahan and pin exactly three for comparison.
7. Open **Analytics** for category totals, subtype composition, score distribution,
   and all 267 representative observations.
8. Open **Methodology** for taxonomy rules, source URLs, licences, checksums,
   scoring version, fingerprint, and interpretation limits.

## 4. Interpretation limits

- OpenStreetMap completeness varies and is not a commercial census.
- Population is a verified annual kelurahan aggregate, not real-time footfall.
- Each kelurahan score uses one in-polygon representative point and does not
  claim uniform suitability across the polygon.
- Scores support comparative screening; they do not predict or guarantee success.
- The population source remains pinned to verified period 2025 until a newer
  official period passes the same validation workflow.

## 5. Cost and offline behavior

The default demo reads its basemap, labels, businesses, and analysis from local
Docker services. No Google Maps key, paid tiles, subscription API, auth provider,
payment system, or billing configuration is used. The optional online map fallback
is a recovery control and is not needed for the offline acceptance test.

## 6. Troubleshooting

- **Configuration unavailable / 404:** restart the backend after source changes:
  `docker compose restart backend`.
- **Hostname blocked in Docker E2E:** ensure `frontend` remains in Vite's explicit
  `server.allowedHosts` list.
- **Tile error:** confirm the active release's PMTiles exists, restart `tiles`, run
  `verify-tile-service`, then use **Retry map**.
- **Opportunity API returns 409:** the release is incomplete or v1; prepare and
  activate a complete v2 release rather than generating unversioned records.
- **Source download fails:** keep the active release; inspect the official endpoint
  and use the retained checksum-verified workflow only when its manifests match.
- **Reset containers:** `docker compose down` preserves data. Do not add `-v`
  unless intentionally deleting the Postgres volume.
