from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime

from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Business, BusinessCategory, DatasetSource, ImportRun
from app.imports.contracts import ImportManifest, ImportQualityReport, SourceIdentity
from app.imports.osm import OsmBusinessRecord
from app.imports.quality import ImportQualityError, assert_demo_quality


class DuplicateSourceRecordError(ValueError):
    pass


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
