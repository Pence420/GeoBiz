from datetime import date, datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DataRelease, DataReleaseSource, DatasetSource


class DatasetSnapshot(BaseModel):
    slug: str
    provider: str
    source_url: str
    license_name: str
    attribution: str
    observed_at: date | None
    retrieved_at: datetime
    sha256: str


def active_release(session: Session) -> DataRelease:
    release = session.scalar(
        select(DataRelease).where(DataRelease.status == "active")
    )
    if release is None:
        raise LookupError("no active data release is available")
    return release


def active_release_id(session: Session) -> int:
    return active_release(session).id


def current_dataset_fingerprint(session: Session) -> str:
    return active_release(session).dataset_fingerprint


def list_dataset_snapshots(session: Session) -> list[DatasetSnapshot]:
    release_id = active_release_id(session)
    sources = session.scalars(
        select(DatasetSource)
        .join(
            DataReleaseSource,
            DataReleaseSource.dataset_source_id == DatasetSource.id,
        )
        .where(DataReleaseSource.data_release_id == release_id)
        .order_by(DatasetSource.slug)
    ).all()
    return [
        DatasetSnapshot(
            slug=source.slug,
            provider=source.provider,
            source_url=source.source_url,
            license_name=source.license_name,
            attribution=source.attribution,
            observed_at=source.observed_at,
            retrieved_at=source.retrieved_at,
            sha256=source.sha256,
        )
        for source in sources
    ]
