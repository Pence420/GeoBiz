# GeoBiz academic demo runbook

This runbook reproduces and verifies the DKI Jakarta MVP without a paid service.
It assumes Docker Desktop or Colima is running and ports 5173, 8000, and 5432 are
available.

## 1. Start the stack

```bash
cp .env.example .env
docker compose up -d --build
make migrate
```

The dashboard is at <http://localhost:5173>, API documentation is at
<http://localhost:8000/docs>, and the health check is at
<http://localhost:8000/api/health>.

## 2. Reproduce the real data snapshot

Raw source files are intentionally excluded from Git because they are large.
Download the files named by the committed manifests and follow the complete,
checksum-verified promotion commands in [`../data/README.md`](../data/README.md).
The order is: businesses and boundary, official TransJakarta GTFS, contextual
OpenStreetMap POIs and roads, official population, normalization profiles, then
opportunity scores.

After promotion, generate derived records:

```bash
make profiles
make opportunities
```

Do not insert invented names or coordinates. Synthetic fixtures belong only in
the isolated automated-test transactions.

## 3. Verify before presenting

```bash
make test
make build-frontend
make lint
docker compose config --quiet
```

The integration suite enforces these demo invariants:

- exactly 1,826 restaurant, 53 gym, and 305 pharmacy records in the promoted snapshot;
- every business has a source identity and valid DKI geometry;
- no provider is named fake, fixture, synthetic, or seed;
- 267 population-matched kelurahan;
- all 15 category/radius opportunity scopes are complete.

## 4. Suggested presentation flow

1. Open **Map explorer** and show the OpenFreeMap attribution.
2. Switch between Restaurant, Gym, and Pharmacy; explain that all points retain
   their OpenStreetMap identity.
3. Toggle competitor clusters, heatmap, population, opportunity, transit,
   commercial, education, offices, and road network.
4. Search for an area/business or enter a coordinate, then click the map to
   recalculate the radius analysis.
5. Change radius and explain the live spatial counts, normalized factors, and
   incomplete-data behavior.
6. Filter opportunity areas, open a ranked representative point, and pin up to
   three areas for comparison.
7. Open **Analytics** for score distribution and population-versus-competition.
8. Open **Methodology** to show source URLs, licences, retrieval dates, scoring
   version, dataset fingerprint, weights, and limitations.

## 5. Interpretation limits

- OpenStreetMap completeness varies and its POIs are not a commercial census.
- Population is an annual kelurahan aggregate, not real-time footfall.
- Each kelurahan score is calculated at one in-polygon representative point; it
  does not assert uniform suitability across the polygon.
- The score supports initial screening and is not a prediction or guarantee of
  business success.

## 6. Cost and external dependencies

GeoBiz uses PostgreSQL/PostGIS, FastAPI, React, MapLibre GL JS, and the public
OpenFreeMap style. There is no Google Maps key, subscription API, authentication,
payment system, or billing configuration. Internet access is only needed to load
the public basemap in the browser; analysis data remains in the local database.

## 7. Troubleshooting

- **Opportunity API returns 409:** run `make profiles` followed by
  `make opportunities` after all datasets are promoted.
- **Basemap is blank:** confirm internet access, use **Retry map**, or continue
  demonstrating the analysis panels; the local results remain available.
- **Port conflict:** change the host-side port in `compose.yaml`, then update
  `VITE_API_BASE_URL` when changing the API port.
- **Stale results after importing data:** regenerate profiles and opportunities;
  both are bound to the combined dataset fingerprint.
- **Reset only application containers:** use `docker compose down`. Do not add
  `-v` unless you intentionally want to delete the local Postgres volume.
