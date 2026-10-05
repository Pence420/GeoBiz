#!/usr/bin/env bash
set -Eeuo pipefail

release_key="offline-map-$(date -u +%Y%m%d%H%M%S)-$$"
partial_tile="data/tiles/releases/${release_key}.partial.pmtiles"
final_tile="data/tiles/releases/${release_key}.pmtiles"

record_failure() {
  status=$?
  rm -f -- "$partial_tile"
  if [ "$status" -ne 0 ]; then
    docker compose run --rm backend python -m app.imports.cli refresh-fail \
      --release-key "$release_key" \
      --phase "offline_map" \
      --message "offline basemap preparation failed with exit code ${status}" || true
  fi
  exit "$status"
}
trap record_failure EXIT

mkdir -p data/tiles/releases data/tiles/tmp
echo "Offline-map-only successors require an active release with a retained verified PBF." >&2
docker compose run --rm backend python -m app.imports.cli offline-map-prepare \
  --release-key "$release_key"
docker compose run --rm tilemaker \
  --input "/data/refresh/${release_key}/raw/jakarta.osm.pbf" \
  --output "/data/tiles/releases/${release_key}.partial.pmtiles" \
  --config /data/tiles/config/geobiz.json \
  --process /data/tiles/config/geobiz.lua \
  --store "/data/tiles/tmp/${release_key}" \
  --skip-integrity
mv -- "$partial_tile" "$final_tile"
docker compose restart tiles
docker compose run --rm backend python -m app.imports.cli verify-tile-service \
  --release-key "$release_key"
docker compose run --rm backend python -m app.imports.cli refresh-activate \
  --release-key "$release_key" \
  --tile "/data/tiles/releases/${release_key}.pmtiles"
trap - EXIT
