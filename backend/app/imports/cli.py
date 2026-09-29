import json
import argparse
from pathlib import Path

from app.db.session import SessionLocal
from app.imports.manifest import load_verified_manifest
from app.imports.administrative import boundary_geometry
from app.imports.gtfs import filter_gtfs_to_boundary, parse_gtfs_stops
from app.imports.promotion import (
    promote_dki_boundary,
    promote_gtfs_stops,
    promote_osm_records,
)
from app.imports.staging import (
    load_staging_batch,
    stage_osm_pbf,
    write_staging_batch,
)


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

    report = commands.add_parser("report", help="print a quality report")
    report.add_argument("path", type=Path)
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
                session, manifest, batch.records, batch.quality_report
            )
            session.commit()
        print(f"promoted import run {import_run_id}")
        return

    if args.command == "promote-boundary":
        manifest = load_verified_manifest(args.manifest, args.raw)
        payload = json.loads(args.raw.read_text(encoding="utf-8"))
        with SessionLocal() as session:
            import_run_id = promote_dki_boundary(session, manifest, payload)
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
                session, manifest, records, quality_report
            )
            session.commit()
        print(quality_report.model_dump_json(indent=2))
        print(f"promoted GTFS import run {import_run_id}")
        return

    print(args.path.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()
