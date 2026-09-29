from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.db.models import Business, DatasetSource
from app.imports.contracts import ImportManifest, ImportQualityReport, SourceIdentity
from app.imports.osm import OsmBusinessRecord
from app.imports.promotion import DuplicateSourceRecordError, promote_osm_records
from app.imports.quality import ImportQualityError


def _manifest(slug: str) -> ImportManifest:
    return ImportManifest(
        dataset_slug=slug,
        source_name="Synthetic integration fixture",
        source_url="https://example.test/osm.pbf",
        source_license="test-only",
        source_observed_at=None,
        retrieved_at=datetime.now(UTC),
        sha256="a" * 64,
        local_filename="fixture.osm.pbf",
    )


def _record(record_id: str, category: str) -> OsmBusinessRecord:
    return OsmBusinessRecord(
        identity=SourceIdentity(
            provider="osm", source_type="node", source_record_id=record_id
        ),
        category_slug=category,
        name=f"Fixture {record_id}",
        latitude=-6.2,
        longitude=106.8,
        tags={"test_only": "true"},
    )


def _report(promoted: int = 3) -> ImportQualityReport:
    return ImportQualityReport(
        total_records=promoted,
        promoted_records=promoted,
        invalid_geometry_count=0,
        missing_name_count=0,
        exact_duplicate_count=0,
        duplicate_candidate_count=0,
        administrative_join_rate=None,
        category_counts={"restaurant": 1, "gym": 1, "pharmacy": 1},
        failures=[],
    )


def test_rejected_batch_does_not_partially_promote(db_session) -> None:
    manifest = _manifest("test-rejected-import")
    invalid_report = _report()
    invalid_report.invalid_geometry_count = 1

    with pytest.raises(ImportQualityError):
        promote_osm_records(
            db_session,
            manifest,
            [_record("1", "restaurant")],
            invalid_report,
        )

    assert db_session.scalar(
        select(func.count()).select_from(DatasetSource).where(
            DatasetSource.slug == manifest.dataset_slug
        )
    ) == 0


def test_snapshot_replacement_is_atomic_and_does_not_duplicate_rows(db_session) -> None:
    manifest = _manifest("test-repeatable-import")
    records = [
        _record("1", "restaurant"),
        _record("2", "gym"),
        _record("3", "pharmacy"),
    ]

    promote_osm_records(db_session, manifest, records, _report())
    promote_osm_records(db_session, manifest, records, _report())

    source_id = db_session.scalar(
        select(DatasetSource.id).where(DatasetSource.slug == manifest.dataset_slug)
    )
    assert db_session.scalar(
        select(func.count()).select_from(Business).where(
            Business.dataset_source_id == source_id
        )
    ) == 3


def test_duplicate_source_identity_rejects_whole_batch(db_session) -> None:
    manifest = _manifest("test-duplicate-import")
    record = _record("same", "restaurant")

    with pytest.raises(DuplicateSourceRecordError):
        promote_osm_records(db_session, manifest, [record, record], _report(2))

    assert db_session.scalar(
        select(func.count()).select_from(DatasetSource).where(
            DatasetSource.slug == manifest.dataset_slug
        )
    ) == 0
