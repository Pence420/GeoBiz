#!/usr/bin/env bash
set -Eeuo pipefail

release_key="refresh-$(date -u +%Y%m%d%H%M%S)-$$"
partial="data/tiles/releases/${release_key}.partial.pmtiles"
final="data/tiles/releases/${release_key}.pmtiles"
prepared=0

on_error() {
  status=$?
  if [[ -f "$partial" ]]; then rm -f -- "$partial"; fi
  if [[ "$prepared" == 1 ]]; then
    docker compose run --rm backend python -m app.imports.cli refresh-fail \
      --release-key "$release_key" --phase host-orchestration \
      --message "host refresh orchestration failed with status $status" || true
  fi
  exit "$status"
}
trap on_error ERR

accept_args=()
if [[ "${1:-}" == "--accept-count-change" ]]; then
  accept_args+=("--accept-count-change")
elif [[ $# -gt 0 ]]; then
  echo "usage: $0 [--accept-count-change]" >&2
  exit 2
fi

mkdir -p data/tiles/releases
mkdir -p data/tiles/tmp
docker compose run --rm backend python -m app.imports.cli refresh-prepare \
  --release-key "$release_key" "${accept_args[@]}"
prepared=1

docker compose run --rm tilemaker \
  --input "/data/refresh/${release_key}/raw/jakarta.osm.pbf" \
  --output "/data/tiles/releases/${release_key}.partial.pmtiles" \
  --config /data/tiles/config/geobiz.json \
  --process /data/tiles/config/geobiz.lua \
  --store "/data/tiles/tmp/${release_key}" \
  --skip-integrity
mv -- "$partial" "$final"

docker compose restart tiles
docker compose run --rm backend python -m app.imports.cli verify-tile-service \
  --release-key "$release_key"
docker compose run --rm backend python -m app.imports.cli refresh-activate \
  --release-key "$release_key" \
  --tile "/data/tiles/releases/${release_key}.pmtiles"

trap - ERR
