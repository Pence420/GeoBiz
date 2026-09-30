import json
import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel

from app.imports.administrative import boundary_geometry, filter_records_to_boundary
from app.imports.contracts import ImportManifest, ImportQualityReport
from app.imports.manifest import load_verified_manifest
from app.imports.osm import OsmBusinessRecord, parse_osmium_geojson
from app.imports.osm_context import (
    OsmContextQualityReport,
    OsmPoiRecord,
    OsmRoadRecord,
    filter_context_to_boundary,
    parse_osm_context_geojson,
)
from app.imports.quality import assert_demo_quality, build_osm_quality_report
from app.imports.population import (
    JoinedKelurahan,
    PopulationQualityReport,
    join_population_to_boundaries,
    load_population_aliases,
    parse_kelurahan_boundaries,
    parse_population_records,
)

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


def stage_osm_context(
    raw_path: Path,
    manifest_path: Path,
    boundary_path: Path,
    boundary_manifest_path: Path,
) -> tuple[
    ImportManifest,
    list[OsmPoiRecord],
    list[OsmRoadRecord],
    OsmContextQualityReport,
]:
    manifest = load_verified_manifest(manifest_path, raw_path)
    load_verified_manifest(boundary_manifest_path, boundary_path)
    with tempfile.TemporaryDirectory(prefix="geobiz-context-") as directory:
        temp = Path(directory)
        poi_pbf = temp / "pois.osm.pbf"
        road_pbf = temp / "roads.osm.pbf"
        poi_geojson = temp / "pois.geojson"
        road_geojson = temp / "roads.geojson"
        _run_osmium_filter(
            raw_path,
            poi_pbf,
            (
                "nwr/shop",
                "nwr/office",
                "nwr/amenity=hospital,clinic,doctors,school,college,university,marketplace,bank",
                "nwr/healthcare=hospital,clinic,doctor,doctors",
            ),
        )
        _run_osmium_filter(
            raw_path,
            road_pbf,
            (
                "w/highway=motorway,motorway_link,trunk,trunk_link,primary,primary_link,secondary,secondary_link",
            ),
        )
        _run_osmium_export(poi_pbf, poi_geojson)
        _run_osmium_export(road_pbf, road_geojson, geometry_types="linestring")
        pois, _ = parse_osm_context_geojson(
            json.loads(poi_geojson.read_text(encoding="utf-8"))
        )
        _, roads = parse_osm_context_geojson(
            json.loads(road_geojson.read_text(encoding="utf-8"))
        )
    geometry = boundary_geometry(
        json.loads(boundary_path.read_text(encoding="utf-8"))
    )
    kept_pois, kept_roads, report = filter_context_to_boundary(
        pois, roads, geometry
    )
    return manifest, kept_pois, kept_roads, report


def _run_osmium_filter(
    raw_path: Path, output_path: Path, expressions: tuple[str, ...]
) -> None:
    subprocess.run(
        [
            "osmium",
            "tags-filter",
            str(raw_path),
            *expressions,
            "-o",
            str(output_path),
            "--overwrite",
        ],
        check=True,
    )


def _run_osmium_export(
    input_path: Path,
    output_path: Path,
    *,
    geometry_types: str | None = None,
) -> None:
    command = [
        "osmium",
        "export",
        str(input_path),
        "--attributes=id,type",
        "--index-type=sparse_file_array",
    ]
    if geometry_types:
        command.append(f"--geometry-types={geometry_types}")
    command.extend(["-o", str(output_path), "--overwrite"])
    subprocess.run(command, check=True)


def stage_population_areas(
    population_path: Path,
    population_manifest_path: Path,
    osm_path: Path,
    geometry_manifest_path: Path,
    province_boundary_path: Path,
    province_boundary_manifest_path: Path,
    aliases_path: Path,
) -> tuple[
    ImportManifest,
    ImportManifest,
    list[JoinedKelurahan],
    PopulationQualityReport,
]:
    population_manifest = load_verified_manifest(
        population_manifest_path, population_path
    )
    geometry_manifest = load_verified_manifest(geometry_manifest_path, osm_path)
    load_verified_manifest(province_boundary_manifest_path, province_boundary_path)
    with tempfile.TemporaryDirectory(prefix="geobiz-admin-") as directory:
        temp = Path(directory)
        filtered_path = temp / "admin.osm.pbf"
        geojson_path = temp / "admin.geojson"
        _run_osmium_filter(
            osm_path, filtered_path, ("r/boundary=administrative",)
        )
        _run_osmium_export(
            filtered_path, geojson_path, geometry_types="polygon"
        )
        admin_payload = json.loads(geojson_path.read_text(encoding="utf-8"))
    population_payload = json.loads(population_path.read_text(encoding="utf-8"))
    province_geometry = boundary_geometry(
        json.loads(province_boundary_path.read_text(encoding="utf-8"))
    )
    populations = parse_population_records(population_payload, period="2025")
    boundaries = parse_kelurahan_boundaries(admin_payload, province_geometry)
    records, report = join_population_to_boundaries(
        populations,
        boundaries,
        aliases=load_population_aliases(aliases_path),
        source_rows=len(population_payload.get("data", [])),
    )
    if report.join_rate < 0.95:
        raise ValueError("population join coverage must be at least 95%")
    return population_manifest, geometry_manifest, records, report
