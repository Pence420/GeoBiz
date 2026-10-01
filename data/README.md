# GeoBiz data workspace

GeoBiz demo data must come from traceable real-world sources. Raw and processed artifacts are intentionally ignored by Git because they can be large and are reproducible from the committed query and manifest metadata.

Rules:

- Never add invented businesses, names, coordinates, or competitor counts.
- Save raw downloads under `data/raw/`.
- Commit the source URL, query, retrieval time, source snapshot time, licence, checksum, and aggregate quality report under `data/manifests/`.
- Keep OpenStreetMap attribution visible in the application: `© OpenStreetMap contributors`.
- Test-only synthetic fixtures belong under `backend/tests/fixtures/` and must never be promoted to the demo database.

The initial business snapshot uses the daily Jakarta `.osm.pbf` extract from
`download.openstreetmap.fr`. The saved Overpass queries remain a smaller-source
fallback. Both paths are offline imports only and are never called by user requests.

## Reproduce the 2026-09-29 business snapshot

Download the raw files named by the committed manifests into `data/raw/`, then run:

```bash
docker compose run --rm backend python -m app.imports.cli stage-osm \
  /data/raw/jakarta.osm.pbf \
  --manifest /data/manifests/osm-dki-businesses-2026-09-29.json \
  --boundary /data/raw/dki-boundary.geojson \
  --boundary-manifest /data/manifests/osm-dki-boundary-2026-09-29.json \
  --output /data/processed/osm-dki-businesses.staged.json \
  --report /data/manifests/osm-dki-businesses-2026-09-29.quality.json

docker compose run --rm backend python -m app.imports.cli promote-osm \
  /data/processed/osm-dki-businesses.staged.json \
  --raw /data/raw/jakarta.osm.pbf \
  --manifest /data/manifests/osm-dki-businesses-2026-09-29.json

docker compose run --rm backend python -m app.imports.cli promote-boundary \
  /data/raw/dki-boundary.geojson \
  --manifest /data/manifests/osm-dki-boundary-2026-09-29.json

docker compose run --rm backend python -m app.imports.cli promote-gtfs \
  /data/raw/transjakarta-gtfs.zip \
  --manifest /data/manifests/transjakarta-gtfs-2026-07-24.json \
  --boundary /data/raw/dki-boundary.geojson \
  --boundary-manifest /data/manifests/osm-dki-boundary-2026-09-29.json \
  --report /data/manifests/transjakarta-gtfs-2026-07-24.quality.json

docker compose run --rm backend python -m app.imports.cli promote-osm-context \
  /data/raw/jakarta.osm.pbf \
  --manifest /data/manifests/osm-dki-context-2026-09-29.json \
  --boundary /data/raw/dki-boundary.geojson \
  --boundary-manifest /data/manifests/osm-dki-boundary-2026-09-29.json \
  --report /data/manifests/osm-dki-context-2026-09-29.quality.json

docker compose run --rm backend python -m app.imports.cli promote-population \
  /data/raw/dki-population-2025.json \
  --manifest /data/manifests/satudata-dki-population-2025.json \
  --osm-raw /data/raw/jakarta.osm.pbf \
  --geometry-manifest /data/manifests/osm-dki-kelurahan-2026-09-29.json \
  --boundary /data/raw/dki-boundary.geojson \
  --boundary-manifest /data/manifests/osm-dki-boundary-2026-09-29.json \
  --aliases /data/crosswalks/dki_kelurahan_aliases.csv \
  --report /data/manifests/satudata-dki-population-2025.quality.json

docker compose run --rm backend python -m app.imports.cli generate-profiles \
  --version v1.0.0 \
  --grid-size-m 1000

docker compose run --rm backend python -m app.imports.cli generate-opportunities \
  --version v1.0.0
```

Promotion replaces the previous snapshot from the same dataset source inside one
database transaction. A checksum mismatch, missing category, invalid geometry,
duplicate source identity, or other failed quality gate aborts the whole batch.
Normalization profiles are generated only after every source has been promoted.
They are bound to the exact combined dataset fingerprint so stale percentiles cannot
silently score newer data. Opportunity scores are then generated for all 267
kelurahan, all three categories, and all five supported radii. Each score uses an
in-polygon representative point (`ST_PointOnSurface`) and retains its raw and
normalized factors; it does not claim that one score is uniform across the polygon.
