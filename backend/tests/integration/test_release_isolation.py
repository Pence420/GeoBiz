from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.analytics.service import search
from app.datasets.service import current_dataset_fingerprint
from app.db.models import BusinessCategory, DataRelease, DatasetSource
from app.releases.service import activate_release, create_staging_release


def _seed_business(
    session: Session,
    *,
    release_id: int,
    source_id: int,
    category_id: int,
    record_id: str,
    name: str,
) -> None:
    session.execute(
        text(
            """
            INSERT INTO businesses (
                data_release_id, category_id, dataset_source_id, name,
                source_type, source_record_id, business_subtype,
                taxonomy_version, retrieved_at, original_tags, geom
            ) VALUES (
                :release_id, :category_id, :source_id, :name,
                'node', :record_id, 'restaurant', 'v2.0.0', now(),
                jsonb_build_object('name', CAST(:name AS text)),
                ST_SetSRID(ST_Point(106.8, -6.2), 4326)
            )
            """
        ),
        {
            "release_id": release_id,
            "category_id": category_id,
            "source_id": source_id,
            "record_id": record_id,
            "name": name,
        },
    )


def test_runtime_queries_only_read_active_release(db_session: Session) -> None:
    old = db_session.scalar(
        select(DataRelease).where(DataRelease.status == "active")
    )
    assert old is not None
    old.dataset_fingerprint = "a" * 64

    source = DatasetSource(
        slug="release-isolation-osm",
        provider="OpenStreetMap",
        source_url="https://www.openstreetmap.org",
        license_name="ODbL-1.0",
        attribution="© OpenStreetMap contributors",
        observed_at=None,
        retrieved_at=old.created_at,
        sha256="c" * 64,
    )
    db_session.add(source)
    db_session.flush()
    category_id = db_session.scalar(
        select(BusinessCategory.id).where(BusinessCategory.slug == "restaurant")
    )
    assert category_id is not None

    new = create_staging_release(
        db_session,
        {
            "release_key": "release-isolation-new",
            "dataset_fingerprint": "b" * 64,
            "taxonomy_version": "v1.0.0",
            "scoring_version": "v1.0.0",
        },
    )
    new.status = "validated"
    _seed_business(
        db_session,
        release_id=old.id,
        source_id=source.id,
        category_id=category_id,
        record_id="old",
        name="ZZX OLD BUSINESS",
    )
    _seed_business(
        db_session,
        release_id=new.id,
        source_id=source.id,
        category_id=category_id,
        record_id="new",
        name="ZZX NEW BUSINESS",
    )
    db_session.flush()

    assert [item.name for item in search(db_session, query="ZZX", limit=10)] == [
        "ZZX OLD BUSINESS"
    ]
    assert current_dataset_fingerprint(db_session) == "a" * 64

    activate_release(db_session, new.id)

    assert [item.name for item in search(db_session, query="ZZX", limit=10)] == [
        "ZZX NEW BUSINESS"
    ]
    assert current_dataset_fingerprint(db_session) == "b" * 64
    db_session.refresh(old)
    assert old.status == "superseded"


def test_database_rejects_two_prepared_releases(db_session: Session) -> None:
    db_session.execute(
        update(DataRelease)
        .where(DataRelease.status.in_(("staging", "validated")))
        .values(status="failed")
    )
    create_staging_release(
        db_session,
        {
            "release_key": "prepared-a",
            "dataset_fingerprint": "a" * 64,
            "taxonomy_version": "v2.0.0",
            "scoring_version": "v2.0.0",
        },
    )
    db_session.flush()

    second = DataRelease(
        release_key="prepared-b",
        status="staging",
        dataset_fingerprint="b" * 64,
        taxonomy_version="v2.0.0",
        scoring_version="v2.0.0",
        combined_manifest={},
    )
    db_session.add(second)

    from sqlalchemy.exc import IntegrityError

    try:
        db_session.flush()
    except IntegrityError:
        return
    raise AssertionError("database accepted two prepared releases")
