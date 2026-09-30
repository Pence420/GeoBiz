from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
import json
from collections.abc import Mapping
from typing import Any

from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.db.models import (
    AdministrativeArea,
    Business,
    BusinessCategory,
    DatasetSource,
    ImportRun,
    Poi,
    Road,
    TransportStop,
)
from app.imports.contracts import ImportManifest, ImportQualityReport, SourceIdentity
from app.imports.osm import OsmBusinessRecord
from app.imports.osm_context import (
    OsmContextQualityReport,
    OsmPoiRecord,
    OsmRoadRecord,
)
from app.imports.gtfs import GtfsQualityReport, GtfsStopRecord
from app.imports.quality import ImportQualityError, assert_demo_quality
from app.imports.population import JoinedKelurahan, PopulationQualityReport


class DuplicateSourceRecordError(ValueError):
    pass


def promote_gtfs_stops(
    session: Session,
    manifest: ImportManifest,
    records: Sequence[GtfsStopRecord],
    report: GtfsQualityReport,
) -> int:
    if report.duplicate_source_id_count:
        raise DuplicateSourceRecordError("GTFS stop IDs must be unique")
    if report.promoted_records != len(records):
        raise ImportQualityError("GTFS quality report does not match staged records")

    with session.begin_nested():
        source = session.scalar(
            select(DatasetSource).where(DatasetSource.slug == manifest.dataset_slug)
        )
        if source is None:
            source = DatasetSource(
                slug=manifest.dataset_slug,
                provider="PT Transportasi Jakarta",
                source_url=str(manifest.source_url),
                license_name=manifest.source_license,
                attribution="GTFS Static Transjakarta © PT Transportasi Jakarta",
                observed_at=manifest.source_observed_at,
                retrieved_at=manifest.retrieved_at,
                sha256=manifest.sha256,
            )
            session.add(source)
            session.flush()
        else:
            source.observed_at = manifest.source_observed_at
            source.retrieved_at = manifest.retrieved_at
            source.sha256 = manifest.sha256

        session.execute(
            delete(TransportStop).where(TransportStop.dataset_source_id == source.id)
        )
        by_source_id: dict[str, TransportStop] = {}
        ordered_records = sorted(
            records, key=lambda record: record.parent_source_record_id is not None
        )
        for record in ordered_records:
            stop = TransportStop(
                dataset_source_id=source.id,
                name=record.name,
                transport_type=record.transport_type,
                source_record_id=record.source_record_id,
                parent_stop_id=None,
                retrieved_at=manifest.retrieved_at,
                original_properties=record.properties,
                geom=WKTElement(
                    f"POINT({record.longitude} {record.latitude})", srid=4326
                ),
            )
            session.add(stop)
            session.flush()
            by_source_id[record.source_record_id] = stop
            if record.parent_source_record_id in by_source_id:
                stop.parent_stop_id = by_source_id[record.parent_source_record_id].id

        run = ImportRun(
            dataset_source_id=source.id,
            status="promoted",
            manifest=manifest.model_dump(mode="json"),
            quality_report=report.model_dump(mode="json"),
            completed_at=datetime.now(UTC),
        )
        session.add(run)
        session.flush()
        return run.id


def promote_osm_context(
    session: Session,
    manifest: ImportManifest,
    pois: Sequence[OsmPoiRecord],
    roads: Sequence[OsmRoadRecord],
    report: OsmContextQualityReport,
) -> int:
    if report.duplicate_source_id_count:
        raise DuplicateSourceRecordError("OSM context source identities must be unique")
    if report.promoted_pois != len(pois) or report.promoted_roads != len(roads):
        raise ImportQualityError("OSM context report does not match staged records")

    with session.begin_nested():
        source = session.scalar(
            select(DatasetSource).where(DatasetSource.slug == manifest.dataset_slug)
        )
        if source is None:
            source = DatasetSource(
                slug=manifest.dataset_slug,
                provider="OpenStreetMap",
                source_url=str(manifest.source_url),
                license_name=manifest.source_license,
                attribution="© OpenStreetMap contributors",
                observed_at=manifest.source_observed_at,
                retrieved_at=manifest.retrieved_at,
                sha256=manifest.sha256,
            )
            session.add(source)
            session.flush()
        else:
            source.observed_at = manifest.source_observed_at
            source.retrieved_at = manifest.retrieved_at
            source.sha256 = manifest.sha256

        session.execute(delete(Poi).where(Poi.dataset_source_id == source.id))
        session.execute(delete(Road).where(Road.dataset_source_id == source.id))
        if pois:
            session.execute(
                text(
                    """
                    INSERT INTO pois (
                        dataset_source_id, name, poi_type, source_type,
                        source_record_id, retrieved_at, original_tags, geom
                    ) VALUES (
                        :dataset_source_id, :name, :poi_type, :source_type,
                        :source_record_id, :retrieved_at, CAST(:tags AS jsonb),
                        ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326)
                    )
                    """
                ),
                [
                    {
                        "dataset_source_id": source.id,
                        "name": record.name,
                        "poi_type": record.poi_type,
                        "source_type": record.source_type,
                        "source_record_id": record.source_record_id,
                        "retrieved_at": manifest.retrieved_at,
                        "tags": json.dumps(record.tags),
                        "geometry": json.dumps(record.geometry),
                    }
                    for record in pois
                ],
            )
        if roads:
            session.execute(
                text(
                    """
                    INSERT INTO roads (
                        dataset_source_id, name, road_type, source_type,
                        source_record_id, retrieved_at, original_tags, geom
                    ) VALUES (
                        :dataset_source_id, :name, :road_type, :source_type,
                        :source_record_id, :retrieved_at, CAST(:tags AS jsonb),
                        ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326))
                    )
                    """
                ),
                [
                    {
                        "dataset_source_id": source.id,
                        "name": record.name,
                        "road_type": record.road_type,
                        "source_type": record.source_type,
                        "source_record_id": record.source_record_id,
                        "retrieved_at": manifest.retrieved_at,
                        "tags": json.dumps(record.tags),
                        "geometry": json.dumps(record.geometry),
                    }
                    for record in roads
                ],
            )
        run = ImportRun(
            dataset_source_id=source.id,
            status="promoted",
            manifest=manifest.model_dump(mode="json"),
            quality_report=report.model_dump(mode="json"),
            completed_at=datetime.now(UTC),
        )
        session.add(run)
        session.flush()
        return run.id


def promote_population_areas(
    session: Session,
    population_manifest: ImportManifest,
    geometry_manifest: ImportManifest,
    records: Sequence[JoinedKelurahan],
    report: PopulationQualityReport,
) -> int:
    if report.join_rate < 0.95:
        raise ImportQualityError("population join coverage must be at least 95%")
    if report.joined_areas != len(records):
        raise ImportQualityError("population report does not match joined areas")

    with session.begin_nested():
        geometry_source = _upsert_dataset_source(
            session,
            geometry_manifest,
            provider="OpenStreetMap",
            attribution="© OpenStreetMap contributors",
        )
        population_source = _upsert_dataset_source(
            session,
            population_manifest,
            provider="Satu Data Jakarta / Dukcapil DKI Jakarta",
            attribution="Satu Data Jakarta — population period 2025",
        )
        session.execute(
            delete(AdministrativeArea).where(
                AdministrativeArea.dataset_source_id == geometry_source.id
            )
        )
        session.execute(
            text(
                """
                INSERT INTO administrative_areas (
                    dataset_source_id, source_record_id, official_code, name,
                    area_type, population, population_density, observed_at,
                    retrieved_at, original_properties, geom
                ) VALUES (
                    :dataset_source_id, :source_record_id, NULL, :name,
                    'kelurahan', :population, NULL, :observed_at,
                    :retrieved_at, CAST(:properties AS jsonb),
                    ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326))
                )
                """
            ),
            [
                {
                    "dataset_source_id": geometry_source.id,
                    "source_record_id": record.source_record_id,
                    "name": record.name,
                    "population": record.population,
                    "observed_at": population_manifest.source_observed_at,
                    "retrieved_at": population_manifest.retrieved_at,
                    "properties": json.dumps(
                        {
                            **record.properties,
                            "population_source": population_manifest.dataset_slug,
                            "wilayah": record.wilayah,
                            "kecamatan": record.kecamatan,
                        }
                    ),
                    "geometry": json.dumps(record.geometry),
                }
                for record in records
            ],
        )
        session.execute(
            text(
                """
                UPDATE administrative_areas
                SET population_density = population / NULLIF(
                    ST_Area(geom::geography) / 1000000.0,
                    0
                )
                WHERE dataset_source_id = :source_id
                """
            ),
            {"source_id": geometry_source.id},
        )
        run = ImportRun(
            dataset_source_id=population_source.id,
            status="promoted",
            manifest={
                "population": population_manifest.model_dump(mode="json"),
                "geometry": geometry_manifest.model_dump(mode="json"),
            },
            quality_report=report.model_dump(mode="json"),
            completed_at=datetime.now(UTC),
        )
        session.add(run)
        session.flush()
        return run.id


def _upsert_dataset_source(
    session: Session,
    manifest: ImportManifest,
    *,
    provider: str,
    attribution: str,
) -> DatasetSource:
    source = session.scalar(
        select(DatasetSource).where(DatasetSource.slug == manifest.dataset_slug)
    )
    if source is None:
        source = DatasetSource(
            slug=manifest.dataset_slug,
            provider=provider,
            source_url=str(manifest.source_url),
            license_name=manifest.source_license,
            attribution=attribution,
            observed_at=manifest.source_observed_at,
            retrieved_at=manifest.retrieved_at,
            sha256=manifest.sha256,
        )
        session.add(source)
        session.flush()
    else:
        source.provider = provider
        source.source_url = str(manifest.source_url)
        source.license_name = manifest.source_license
        source.attribution = attribution
        source.observed_at = manifest.source_observed_at
        source.retrieved_at = manifest.retrieved_at
        source.sha256 = manifest.sha256
    return source


def promote_dki_boundary(
    session: Session,
    manifest: ImportManifest,
    payload: Mapping[str, Any],
) -> int:
    from app.imports.administrative import boundary_geometry

    geometry = boundary_geometry(payload)
    features = payload.get("features", [])
    properties = features[0].get("properties", {}) if features else {}
    if not isinstance(properties, Mapping):
        properties = {}
    source_type = str(properties.get("osm_type", "relation"))
    source_id = str(properties.get("osm_id", "6362934"))
    area_name = str(properties.get("name", "Daerah Khusus Ibukota Jakarta"))

    with session.begin_nested():
        source = session.scalar(
            select(DatasetSource).where(DatasetSource.slug == manifest.dataset_slug)
        )
        if source is None:
            source = DatasetSource(
                slug=manifest.dataset_slug,
                provider="OpenStreetMap",
                source_url=str(manifest.source_url),
                license_name=manifest.source_license,
                attribution="© OpenStreetMap contributors",
                observed_at=manifest.source_observed_at,
                retrieved_at=manifest.retrieved_at,
                sha256=manifest.sha256,
            )
            session.add(source)
            session.flush()
        else:
            source.observed_at = manifest.source_observed_at
            source.retrieved_at = manifest.retrieved_at
            source.sha256 = manifest.sha256

        session.execute(
            delete(AdministrativeArea).where(
                AdministrativeArea.dataset_source_id == source.id
            )
        )
        area = AdministrativeArea(
            dataset_source_id=source.id,
            source_record_id=f"{source_type}/{source_id}",
            official_code="ID-JK",
            name=area_name,
            area_type="province",
            population=None,
            population_density=None,
            observed_at=manifest.source_observed_at,
            retrieved_at=manifest.retrieved_at,
            original_properties=dict(properties),
            geom=func.ST_Multi(
                func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geometry)), 4326)
            ),
        )
        session.add(area)
        session.flush()
        valid = session.scalar(
            select(func.ST_IsValid(AdministrativeArea.geom)).where(
                AdministrativeArea.id == area.id
            )
        )
        if not valid:
            raise ValueError("DKI boundary geometry is invalid")
        run = ImportRun(
            dataset_source_id=source.id,
            status="promoted",
            manifest=manifest.model_dump(mode="json"),
            quality_report={"total_records": 1, "promoted_records": 1},
            completed_at=datetime.now(UTC),
        )
        session.add(run)
        session.flush()
        return run.id


def promote_osm_records(
    session: Session,
    manifest: ImportManifest,
    records: Sequence[OsmBusinessRecord],
    report: ImportQualityReport,
) -> int:
    _validate_batch(records, report)
    assert_demo_quality(report)

    with session.begin_nested():
        source = session.scalar(
            select(DatasetSource).where(DatasetSource.slug == manifest.dataset_slug)
        )
        if source is None:
            source = DatasetSource(
                slug=manifest.dataset_slug,
                provider="OpenStreetMap",
                source_url=str(manifest.source_url),
                license_name=manifest.source_license,
                attribution="© OpenStreetMap contributors",
                observed_at=manifest.source_observed_at,
                retrieved_at=manifest.retrieved_at,
                sha256=manifest.sha256,
            )
            session.add(source)
            session.flush()
        else:
            source.source_url = str(manifest.source_url)
            source.license_name = manifest.source_license
            source.observed_at = manifest.source_observed_at
            source.retrieved_at = manifest.retrieved_at
            source.sha256 = manifest.sha256

        category_ids = dict(
            session.execute(
                select(BusinessCategory.slug, BusinessCategory.id).where(
                    BusinessCategory.slug.in_({record.category_slug for record in records})
                )
            ).all()
        )
        missing_categories = sorted(
            {record.category_slug for record in records} - category_ids.keys()
        )
        if missing_categories:
            raise ImportQualityError(
                "database is missing supported categories: " + ", ".join(missing_categories)
            )

        session.execute(
            delete(Business).where(Business.dataset_source_id == source.id)
        )
        session.add_all(
            Business(
                category_id=category_ids[record.category_slug],
                dataset_source_id=source.id,
                name=record.name,
                source_type=record.identity.source_type,
                source_record_id=record.identity.source_record_id,
                source_observed_at=manifest.source_observed_at,
                retrieved_at=manifest.retrieved_at,
                original_tags=record.tags,
                geom=WKTElement(
                    f"POINT({record.longitude} {record.latitude})", srid=4326
                ),
            )
            for record in records
        )
        import_run = ImportRun(
            dataset_source_id=source.id,
            status="promoted",
            manifest=manifest.model_dump(mode="json"),
            quality_report=report.model_dump(mode="json"),
            completed_at=datetime.now(UTC),
        )
        session.add(import_run)
        session.flush()
        return import_run.id


def _validate_batch(
    records: Sequence[OsmBusinessRecord], report: ImportQualityReport
) -> None:
    identities: set[SourceIdentity] = set()
    for record in records:
        if record.identity in identities:
            raise DuplicateSourceRecordError(
                "duplicate source identity in batch: "
                f"{record.identity.source_type}/{record.identity.source_record_id}"
            )
        identities.add(record.identity)

    category_counts = dict(Counter(record.category_slug for record in records))
    if report.promoted_records != len(records):
        raise ImportQualityError("quality report promoted count does not match batch")
    if report.category_counts != category_counts:
        raise ImportQualityError("quality report category counts do not match batch")
