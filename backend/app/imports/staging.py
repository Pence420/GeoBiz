import json
import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel

from app.imports.administrative import boundary_geometry, filter_records_to_boundary
from app.imports.contracts import ImportManifest, ImportQualityReport
from app.imports.manifest import load_verified_manifest
from app.imports.osm import OsmBusinessRecord, parse_osmium_geojson
from app.imports.quality import assert_demo_quality, build_osm_quality_report

OSM_BUSINESS_FILTERS = (
    "nwr/amenity=restaurant",
    "nwr/leisure=fitness_centre",
    "nwr/amenity=pharmacy",
    "nwr/healthcare=pharmacy",
)


class OsmStagingBatch(BaseModel):
    manifest_sha256: str
    boundary_sha256: str
    records: list[OsmBusinessRecord]
    quality_report: ImportQualityReport


def stage_osm_pbf(
    raw_path: Path,
    manifest_path: Path,
    boundary_path: Path,
    boundary_manifest_path: Path,
) -> tuple[ImportManifest, OsmStagingBatch]:
    manifest = load_verified_manifest(manifest_path, raw_path)
    boundary_manifest = load_verified_manifest(boundary_manifest_path, boundary_path)

    with tempfile.TemporaryDirectory(prefix="geobiz-osm-") as directory:
        filtered_path = Path(directory) / "businesses.osm.pbf"
        geojson_path = Path(directory) / "businesses.geojson"
        subprocess.run(
            [
                "osmium",
                "tags-filter",
                str(raw_path),
                *OSM_BUSINESS_FILTERS,
                "-o",
                str(filtered_path),
                "--overwrite",
            ],
            check=True,
        )
        subprocess.run(
            [
                "osmium",
                "export",
                str(filtered_path),
                "--attributes=id,type",
                "-o",
                str(geojson_path),
                "--overwrite",
            ],
            check=True,
        )
        payload = json.loads(geojson_path.read_text(encoding="utf-8"))

    parsed_records = parse_osmium_geojson(payload)
    geometry = boundary_geometry(
        json.loads(boundary_path.read_text(encoding="utf-8"))
    )
    records, outside_count = filter_records_to_boundary(parsed_records, geometry)
    report = build_osm_quality_report(
        records,
        total_records=len(parsed_records),
        outside_coverage_count=outside_count,
    )
    assert_demo_quality(report)
    return manifest, OsmStagingBatch(
        manifest_sha256=manifest.sha256,
        boundary_sha256=boundary_manifest.sha256,
        records=records,
        quality_report=report,
    )


def write_staging_batch(
    batch: OsmStagingBatch, output_path: Path, report_path: Path
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        batch.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    report_path.write_text(
        batch.quality_report.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )


def load_staging_batch(path: Path) -> OsmStagingBatch:
    return OsmStagingBatch.model_validate_json(path.read_text(encoding="utf-8"))
