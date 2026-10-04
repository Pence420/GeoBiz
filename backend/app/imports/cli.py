import json
import argparse
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.db.models import DataRelease
from app.datasets.service import active_release_id
from app.imports.manifest import load_verified_manifest
from app.imports.administrative import boundary_geometry
from app.imports.gtfs import filter_gtfs_to_boundary, parse_gtfs_stops
from app.imports.promotion import (
    promote_dki_boundary,
    promote_gtfs_stops,
    promote_osm_context,
    promote_osm_records,
    promote_population_areas,
)
from app.imports.staging import (
    load_staging_batch,
    stage_osm_context,
    stage_osm_pbf,
    stage_population_areas,
    write_staging_batch,
)
from app.scoring.generator import generate_normalization_profiles
from app.areas.generator import generate_opportunity_scores
from app.refresh.config import RefreshConfig
from app.refresh.orchestrator import RefreshOrchestrator, build_default_hooks
from app.refresh.tiles import verify_tile_service
from app.releases.service import fail_release, rollback_release

DEFAULT_REFRESH_CONFIG = Path("/data/sources/geobiz-v2.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GeoBiz offline data importer")
    commands = parser.add_subparsers(dest="command", required=True)

    stage = commands.add_parser("stage-osm", help="verify, extract, and validate OSM")
    stage.add_argument("raw", type=Path)
    stage.add_argument("--manifest", type=Path, required=True)
    stage.add_argument("--boundary", type=Path, required=True)
    stage.add_argument("--boundary-manifest", type=Path, required=True)
    stage.add_argument("--output", type=Path, required=True)
    stage.add_argument("--report", type=Path, required=True)

    promote = commands.add_parser("promote-osm", help="atomically load staged OSM")
    promote.add_argument("staged", type=Path)
    promote.add_argument("--raw", type=Path, required=True)
    promote.add_argument("--manifest", type=Path, required=True)

    boundary = commands.add_parser(
        "promote-boundary", help="verify and atomically load the DKI boundary"
    )
    boundary.add_argument("raw", type=Path)
    boundary.add_argument("--manifest", type=Path, required=True)

    gtfs = commands.add_parser("promote-gtfs", help="verify and load official GTFS stops")
    gtfs.add_argument("raw", type=Path)
    gtfs.add_argument("--manifest", type=Path, required=True)
    gtfs.add_argument("--boundary", type=Path, required=True)
    gtfs.add_argument("--boundary-manifest", type=Path, required=True)
    gtfs.add_argument("--report", type=Path, required=True)

    context = commands.add_parser(
        "promote-osm-context", help="extract and load OSM POIs and major roads"
    )
    context.add_argument("raw", type=Path)
    context.add_argument("--manifest", type=Path, required=True)
    context.add_argument("--boundary", type=Path, required=True)
    context.add_argument("--boundary-manifest", type=Path, required=True)
    context.add_argument("--report", type=Path, required=True)

    population = commands.add_parser(
        "promote-population", help="join official population to kelurahan geometry"
    )
    population.add_argument("raw", type=Path)
    population.add_argument("--manifest", type=Path, required=True)
    population.add_argument("--osm-raw", type=Path, required=True)
    population.add_argument("--geometry-manifest", type=Path, required=True)
    population.add_argument("--boundary", type=Path, required=True)
    population.add_argument("--boundary-manifest", type=Path, required=True)
    population.add_argument("--aliases", type=Path, required=True)
    population.add_argument("--report", type=Path, required=True)

    profiles = commands.add_parser(
        "generate-profiles", help="build DKI-wide versioned score profiles"
    )
    profiles.add_argument("--version", default="v1.0.0")
    profiles.add_argument("--grid-size-m", type=int, default=1000)

    opportunities = commands.add_parser(
        "generate-opportunities",
        help="cache versioned point-on-surface scores for every kelurahan",
    )
    opportunities.add_argument("--version", default="v1.0.0")

    report = commands.add_parser("report", help="print a quality report")
    report.add_argument("path", type=Path)

    refresh_prepare = commands.add_parser(
        "refresh-prepare", help="download, validate, and prepare an isolated release"
    )
    refresh_prepare.add_argument("--release-key", required=True)
    refresh_prepare.add_argument("--config", type=Path, default=DEFAULT_REFRESH_CONFIG)
    refresh_prepare.add_argument("--dry-run", action="store_true")
    refresh_prepare.add_argument("--accept-count-change", action="store_true")

    refresh_activate = commands.add_parser(
        "refresh-activate", help="derive and atomically activate a prepared release"
    )
    refresh_activate.add_argument("--release-key", required=True)
    refresh_activate.add_argument("--tile", type=Path, required=True)
    refresh_activate.add_argument("--config", type=Path, default=DEFAULT_REFRESH_CONFIG)

    offline_map_prepare = commands.add_parser(
        "offline-map-prepare",
        help="clone the active data snapshot for an offline basemap-only release",
    )
    offline_map_prepare.add_argument("--release-key", required=True)
    offline_map_prepare.add_argument(
        "--config", type=Path, default=DEFAULT_REFRESH_CONFIG
    )

    local_prepare = commands.add_parser(
        "refresh-prepare-local",
        help="prepare v2 from retained source files and checksum manifests",
    )
    local_prepare.add_argument("--release-key", required=True)
    local_prepare.add_argument("--config", type=Path, default=DEFAULT_REFRESH_CONFIG)
    local_prepare.add_argument("--osm", type=Path, required=True)
    local_prepare.add_argument("--osm-manifest", type=Path, required=True)
    local_prepare.add_argument("--boundary", type=Path, required=True)
    local_prepare.add_argument("--boundary-manifest", type=Path, required=True)
    local_prepare.add_argument("--gtfs", type=Path, required=True)
    local_prepare.add_argument("--gtfs-manifest", type=Path, required=True)
    local_prepare.add_argument("--population", type=Path, required=True)
    local_prepare.add_argument("--population-manifest", type=Path, required=True)
    local_prepare.add_argument("--accept-count-change", action="store_true")

    refresh_fail = commands.add_parser(
        "refresh-fail", help="record failure for an incomplete prepared release"
    )
    refresh_fail.add_argument("--release-key", required=True)
    refresh_fail.add_argument("--phase", required=True)
    refresh_fail.add_argument("--message", required=True)

    commands.add_parser("refresh-status", help="print release lifecycle status")

    rollback = commands.add_parser(
        "rollback-release", help="reactivate the immediately previous healthy release"
    )
    rollback.add_argument("release_key")
    rollback.add_argument("--tile-root", type=Path, default=Path("/data/tiles/releases"))

    verify_tiles = commands.add_parser(
        "verify-tile-service", help="verify Martin catalog and representative DKI tiles"
    )
    verify_tiles.add_argument("--release-key", required=True)
    verify_tiles.add_argument(
        "--base-url", default="http://tiles:3000"
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "stage-osm":
        _, batch = stage_osm_pbf(
            args.raw,
            args.manifest,
            args.boundary,
            args.boundary_manifest,
        )
        write_staging_batch(batch, args.output, args.report)
        print(batch.quality_report.model_dump_json(indent=2))
        return

    if args.command == "promote-osm":
        manifest = load_verified_manifest(args.manifest, args.raw)
        batch = load_staging_batch(args.staged)
        if batch.manifest_sha256 != manifest.sha256:
            raise ValueError("staging batch does not belong to the verified manifest")
        with SessionLocal() as session:
            import_run_id = promote_osm_records(
                session,
                active_release_id(session),
                manifest,
                batch.records,
                batch.quality_report,
            )
            session.commit()
        print(f"promoted import run {import_run_id}")
        return

    if args.command == "promote-boundary":
        manifest = load_verified_manifest(args.manifest, args.raw)
        payload = json.loads(args.raw.read_text(encoding="utf-8"))
        with SessionLocal() as session:
            import_run_id = promote_dki_boundary(
                session, active_release_id(session), manifest, payload
            )
            session.commit()
        print(f"promoted boundary import run {import_run_id}")
        return

    if args.command == "promote-gtfs":
        manifest = load_verified_manifest(args.manifest, args.raw)
        load_verified_manifest(args.boundary_manifest, args.boundary)
        geometry = boundary_geometry(
            json.loads(args.boundary.read_text(encoding="utf-8"))
        )
        records, quality_report = filter_gtfs_to_boundary(
            parse_gtfs_stops(args.raw), geometry
        )
        args.report.write_text(
            quality_report.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        with SessionLocal() as session:
            import_run_id = promote_gtfs_stops(
                session,
                active_release_id(session),
                manifest,
                records,
                quality_report,
            )
            session.commit()
        print(quality_report.model_dump_json(indent=2))
        print(f"promoted GTFS import run {import_run_id}")
        return

    if args.command == "promote-osm-context":
        manifest, pois, roads, quality_report = stage_osm_context(
            args.raw,
            args.manifest,
            args.boundary,
            args.boundary_manifest,
        )
        args.report.write_text(
            quality_report.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        with SessionLocal() as session:
            import_run_id = promote_osm_context(
                session,
                active_release_id(session),
                manifest,
                pois,
                roads,
                quality_report,
            )
            session.commit()
        print(quality_report.model_dump_json(indent=2))
        print(f"promoted OSM context import run {import_run_id}")
        return

    if args.command == "promote-population":
        population_manifest, geometry_manifest, records, quality_report = (
            stage_population_areas(
                args.raw,
                args.manifest,
                args.osm_raw,
                args.geometry_manifest,
                args.boundary,
                args.boundary_manifest,
                args.aliases,
            )
        )
        args.report.write_text(
            quality_report.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        with SessionLocal() as session:
            import_run_id = promote_population_areas(
                session,
                active_release_id(session),
                population_manifest,
                geometry_manifest,
                records,
                quality_report,
            )
            session.commit()
        print(quality_report.model_dump_json(indent=2))
        print(f"promoted population import run {import_run_id}")
        return

    if args.command == "generate-profiles":
        with SessionLocal() as session:
            profiles = generate_normalization_profiles(
                session,
                version=args.version,
                grid_size_m=args.grid_size_m,
            )
            summary = [
                {
                    "category_id": profile.category_id,
                    "radius_m": profile.radius_m,
                    "sample_count": profile.sample_count,
                    "fingerprint": profile.dataset_fingerprint,
                }
                for profile in profiles
            ]
            session.commit()
        print(json.dumps(summary, indent=2))
        return

    if args.command == "generate-opportunities":
        with SessionLocal() as session:
            scores = generate_opportunity_scores(session, version=args.version)
            summary = {
                "generated": len(scores),
                "dataset_fingerprint": (
                    scores[0].dataset_fingerprint if scores else None
                ),
                "scoring_version": args.version,
            }
            session.commit()
        print(json.dumps(summary, indent=2))
        return

    if args.command == "refresh-prepare":
        orchestrator = RefreshOrchestrator(
            RefreshConfig.load(args.config), build_default_hooks()
        )
        with SessionLocal() as session:
            result = orchestrator.prepare(
                session,
                release_key=args.release_key,
                dry_run=args.dry_run,
                accept_count_change=args.accept_count_change,
            )
            session.commit()
        print(result.model_dump_json(indent=2))
        return

    if args.command == "refresh-activate":
        orchestrator = RefreshOrchestrator(
            RefreshConfig.load(args.config), build_default_hooks()
        )
        with SessionLocal() as session:
            release = orchestrator.activate(
                session, release_key=args.release_key, tile_path=args.tile
            )
            payload = _release_payload(release)
            session.commit()
        print(json.dumps(payload, indent=2))
        return

    if args.command == "offline-map-prepare":
        orchestrator = RefreshOrchestrator(
            RefreshConfig.load(args.config), build_default_hooks()
        )
        with SessionLocal() as session:
            result = orchestrator.prepare_offline_map(
                session, release_key=args.release_key
            )
            session.commit()
        print(result.model_dump_json(indent=2))
        return

    if args.command == "refresh-prepare-local":
        orchestrator = RefreshOrchestrator(
            RefreshConfig.load(args.config), build_default_hooks()
        )
        source_paths = {
            role: (getattr(args, role), getattr(args, f"{role}_manifest"))
            for role in ("osm", "boundary", "gtfs", "population")
        }
        with SessionLocal() as session:
            result = orchestrator.prepare_local_snapshots(
                session,
                release_key=args.release_key,
                source_paths=source_paths,
                accept_count_change=args.accept_count_change,
            )
            session.commit()
        print(result.model_dump_json(indent=2))
        return

    if args.command == "refresh-fail":
        with SessionLocal() as session:
            release = session.scalar(
                select(DataRelease).where(DataRelease.release_key == args.release_key)
            )
            if release is None:
                raise ValueError(f"release {args.release_key!r} does not exist")
            if release.status != "failed":
                release = fail_release(
                    session, release.id, phase=args.phase, message=args.message
                )
            payload = _release_payload(release)
            session.commit()
        print(json.dumps(payload, indent=2))
        return

    if args.command == "refresh-status":
        with SessionLocal() as session:
            rows = session.scalars(
                select(DataRelease).order_by(DataRelease.created_at.desc())
            ).all()
        payload = {
            "active": next(
                (_release_payload(row) for row in rows if row.status == "active"), None
            ),
            "pending": next(
                (
                    _release_payload(row)
                    for row in rows
                    if row.status in {"staging", "validated"}
                ),
                None,
            ),
            "latest_failed": next(
                (_release_payload(row) for row in rows if row.status == "failed"), None
            ),
        }
        print(json.dumps(payload, indent=2))
        return

    if args.command == "rollback-release":
        with SessionLocal() as session:
            release = rollback_release(
                session, args.release_key, tile_root=args.tile_root
            )
            payload = _release_payload(release)
            session.commit()
        print(json.dumps(payload, indent=2))
        return

    if args.command == "verify-tile-service":
        result = verify_tile_service(args.base_url, args.release_key)
        print(result.model_dump_json(indent=2))
        return

    print(args.path.read_text(encoding="utf-8"), end="")


def _release_payload(release: DataRelease) -> dict:
    return {
        "id": release.id,
        "release_key": release.release_key,
        "status": release.status,
        "dataset_fingerprint": release.dataset_fingerprint,
        "taxonomy_version": release.taxonomy_version,
        "scoring_version": release.scoring_version,
        "tile_filename": release.tile_filename,
        "tile_sha256": release.tile_sha256,
        "failure": release.failure,
        "validated_at": (
            release.validated_at.isoformat() if release.validated_at else None
        ),
        "activated_at": (
            release.activated_at.isoformat() if release.activated_at else None
        ),
    }


if __name__ == "__main__":
    main()
