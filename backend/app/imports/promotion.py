from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
import json
from collections.abc import Mapping
from typing import Any

from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AdministrativeArea,
    Business,
    BusinessCategory,
    DatasetSource,
    ImportRun,
    TransportStop,
)
from app.imports.contracts import ImportManifest, ImportQualityReport, SourceIdentity
from app.imports.osm import OsmBusinessRecord
from app.imports.gtfs import GtfsQualityReport, GtfsStopRecord
from app.imports.quality import ImportQualityError, assert_demo_quality


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
