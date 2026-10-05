# GeoBiz v2 data refresh and rollback

This runbook operates immutable, release-scoped data and offline basemaps. A
failed preparation or activation must leave the currently active release usable.

## Initial setup

```bash
cp .env.example .env
docker compose up -d --build
make migrate
docker compose config --quiet
```

Configuration lives in `data/sources/geobiz-v2.json`. Download hosts are
allow-listed, response sizes are capped, redirects to unapproved hosts are
rejected, and preparation requires at least 2 GB free. Population is pinned to
the verified official 2025 period until a newer period is explicitly configured.

## Inspect and dry-run

```bash
make refresh-status
make refresh-data-dry-run
make refresh-status
```

The second status must show the same active release ID as the first. Dry-run may
report source/schema/HTTP failures, but it must not activate or partially promote
anything. In October 2026 the Satu Data endpoint required POST and had changed
operational behavior; treat any unexpected period/schema as a failed validation,
not permission to relabel data.

Acceptance evidence on 2026-10-05: the dry-run decoded the official BOM-prefixed
GeoJSON correctly, then stopped at the count gate because only 48 of the required
267 populated kelurahan were returned. `demo-v2-20261004` (ID 150) remained active;
the count-change override was intentionally not used.

## Full online refresh

```bash
make refresh-data
```

The script performs: isolated download, checksum/shape validation, count-change
gate, staging, PMTiles build from the exact prepared PBF, tile service verification,
derivation of 15 profiles and 4,005 scores, then atomic activation. On success:

```bash
make refresh-status
docker compose run --rm backend python -m app.imports.cli verify-tile-service \
  --release-key <active-release-key>
```

If a category or supporting-data count decreases by more than 30% or increases
by more than 100%, inspect the quality report and source changes. Only for a
legitimate expected change, rerun explicitly:

```bash
make refresh-data ACCEPT_COUNT_CHANGE=1
```

## Retained verified-source preparation

Run `refresh-prepare-local` exactly as documented in [`../data/README.md`](../data/README.md).
It prints `<release-key>`, `<verified-pbf>`, and `<expected-tile>`. Build only from
that PBF and write first to a partial filename:

```bash
docker compose run --rm tilemaker \
  --input /data/refresh/<release-key>/raw/jakarta.osm.pbf \
  --output /data/tiles/releases/<release-key>.partial.pmtiles \
  --config /data/tiles/config/geobiz.json \
  --process /data/tiles/config/geobiz.lua \
  --store /data/tiles/tmp/<release-key> \
  --skip-integrity

mv data/tiles/releases/<release-key>.partial.pmtiles \
  data/tiles/releases/<release-key>.pmtiles
docker compose restart tiles
docker compose run --rm backend python -m app.imports.cli verify-tile-service \
  --release-key <release-key>
docker compose run --rm backend python -m app.imports.cli refresh-activate \
  --release-key <release-key> \
  --tile /data/tiles/releases/<release-key>.pmtiles
```

Never attach an older PMTiles file to a new release key. The archive must be
built from the exact verified PBF recorded by that release.

## Basemap-only successor

When only the local vector basemap must be rebuilt from the active release's
retained verified PBF:

```bash
make prepare-offline-map
make refresh-status
```

This creates a new immutable successor, verifies it, and activates data and tile
URL together. It does not fetch or invent business records.

## Rollback

Rollback accepts only the immediately previous healthy release and requires its
recorded PMTiles artifact to exist and match checksum:

```bash
make rollback-release RELEASE=<previous-release-key>
make refresh-status
```

Verify `/api/map-config`, `/api/metadata`, category totals/fingerprint, and a
representative tile. To return to the newer release, it must then be the immediate
healthy predecessor in the release chain:

```bash
make rollback-release RELEASE=<newer-release-key>
make refresh-status
```

Release rollback does not downgrade schema. A code rollback across the intentional
v1/v2 category boundary requires the matching database backup.

Acceptance evidence on 2026-10-05: GeoBiz rolled back from
`offline-map-20261004064945-18615` (ID 173) to `demo-v2-20261004` (ID 150), then
reactivated ID 173. Both directions preserved fingerprint
`583033fafa8739f8bcb35ad970edde2781b9cbec9aee13d46570016573f25552` while
`/api/map-config` changed the release-scoped tile URL and SHA-256 together.

## Acceptance and offline demo

```bash
docker compose config --quiet
docker compose run --rm backend pytest -q
docker compose run --rm frontend npm test -- --run
docker compose run --rm frontend npm run lint
docker compose run --rm frontend npm run build
make e2e
```

The offline Playwright test blocks all browser hosts except the local frontend
and still requires the basemap, business evidence, and location score.

## Storage and retention

Inspect usage with `du -sh data/raw data/refresh data/tiles`. Tilemaker temporary
storage can be several GB. Retain the active release, the immediate rollback
release, and at most one older superseded release by default. Never remove an
active/referenced PMTiles, the retained verified PBF, or an immediate rollback
artifact. Pruning is deliberately manual: inspect database release references,
status, and checksums before removing an exact old workspace/artifact.

## Zero-billing statement

Refresh and serving use public source downloads and local open-source Docker
services. No paid API, cloud tile account, API key, payment integration, or
billing configuration is required.
