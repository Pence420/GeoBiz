import hashlib
from datetime import date, datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DatasetSource


class DatasetSnapshot(BaseModel):
    slug: str
    provider: str
    source_url: str
    license_name: str
    attribution: str
    observed_at: date | None
    retrieved_at: datetime
    sha256: str


def current_dataset_fingerprint(session: Session) -> str:
    rows = session.execute(
        select(DatasetSource.slug, DatasetSource.sha256).order_by(DatasetSource.slug)
    ).all()
    if not rows:
        raise LookupError("no promoted datasets are available")
    material = "\n".join(f"{slug}:{checksum}" for slug, checksum in rows)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def list_dataset_snapshots(session: Session) -> list[DatasetSnapshot]:
    sources = session.scalars(select(DatasetSource).order_by(DatasetSource.slug)).all()
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
