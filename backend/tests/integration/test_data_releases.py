from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.datasets.service import active_release
from app.db.models import DataRelease, DatasetSource


def make_release(
    session: Session,
    *,
    release_key: str,
    status: str,
    fingerprint: str,
) -> DataRelease:
    release = DataRelease(
        release_key=release_key,
        status=status,
        dataset_fingerprint=fingerprint,
        taxonomy_version="v2.0.0",
        scoring_version="v2.0.0",
        combined_manifest={},
    )
    session.add(release)
    return release


def supersede_current_release(session: Session) -> None:
    session.execute(
        update(DataRelease)
        .where(DataRelease.status == "active")
        .values(status="superseded")
    )
    session.flush()


def test_database_rejects_two_active_releases(db_session: Session) -> None:
    supersede_current_release(db_session)
    make_release(
        db_session,
        release_key="release-a",
        status="active",
        fingerprint="a" * 64,
    )
    db_session.flush()
    make_release(
        db_session,
        release_key="release-b",
        status="active",
        fingerprint="b" * 64,
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_active_release_returns_the_single_active_row(db_session: Session) -> None:
    supersede_current_release(db_session)
    release = make_release(
        db_session,
        release_key="release-current",
        status="active",
        fingerprint="a" * 64,
    )
    db_session.flush()

    assert active_release(db_session).id == release.id


def test_source_snapshots_are_immutable_per_checksum(db_session: Session) -> None:
    now = datetime.now(UTC)
    first = DatasetSource(
        slug="osm-dki",
        provider="OpenStreetMap",
        source_url="https://download.geofabrik.de/asia/indonesia-latest.osm.pbf",
        license_name="ODbL-1.0",
        attribution="© OpenStreetMap contributors",
        observed_at=None,
        retrieved_at=now,
        sha256="a" * 64,
    )
    second = DatasetSource(
        slug="osm-dki",
        provider="OpenStreetMap",
        source_url="https://download.geofabrik.de/asia/indonesia-latest.osm.pbf",
        license_name="ODbL-1.0",
        attribution="© OpenStreetMap contributors",
        observed_at=None,
        retrieved_at=now,
        sha256="b" * 64,
    )
    db_session.add_all([first, second])
    db_session.flush()

    assert first.id != second.id
