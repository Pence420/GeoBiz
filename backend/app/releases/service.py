from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.models import BusinessCategory, DataRelease

LEGACY_CATEGORY_SLUGS = ("restaurant", "gym", "pharmacy")
V2_CATEGORY_SLUGS = ("fnb", "retail", "services")


class ReleaseStateError(ValueError):
    pass


def create_staging_release(
    session: Session,
    manifest: dict[str, Any],
) -> DataRelease:
    release = DataRelease(
        release_key=str(manifest["release_key"]),
        status="staging",
        dataset_fingerprint=str(manifest["dataset_fingerprint"]),
        taxonomy_version=str(manifest.get("taxonomy_version", "v2.0.0")),
        scoring_version=str(manifest.get("scoring_version", "v2.0.0")),
        combined_manifest=manifest,
    )
    session.add(release)
    session.flush()
    return release


def activate_release(session: Session, release_id: int) -> DataRelease:
    release = session.get(DataRelease, release_id)
    if release is None:
        raise ReleaseStateError(f"data release {release_id} does not exist")
    if release.status != "validated":
        raise ReleaseStateError(
            f"data release {release.release_key} is {release.status}, not validated"
        )

    session.execute(
        update(DataRelease)
        .where(DataRelease.status == "active")
        .values(status="superseded")
    )
    result = session.execute(
        update(DataRelease)
        .where(
            DataRelease.id == release_id,
            DataRelease.status == "validated",
        )
        .values(status="active", activated_at=func.now())
    )
    if result.rowcount != 1:
        raise ReleaseStateError("release activation did not update exactly one row")

    active_slugs = (
        V2_CATEGORY_SLUGS
        if release.taxonomy_version == "v2.0.0"
        else LEGACY_CATEGORY_SLUGS
    )
    session.execute(update(BusinessCategory).values(is_active=False))
    session.execute(
        update(BusinessCategory)
        .where(BusinessCategory.slug.in_(active_slugs))
        .values(is_active=True)
    )
    session.flush()
    session.refresh(release)
    return release


def fail_release(
    session: Session,
    release_id: int,
    *,
    phase: str,
    message: str,
) -> DataRelease:
    release = session.get(DataRelease, release_id)
    if release is None:
        raise ReleaseStateError(f"data release {release_id} does not exist")
    if release.status in {"active", "superseded"}:
        raise ReleaseStateError("published releases cannot be marked failed")
    release.status = "failed"
    release.failure = {
        "phase": phase,
        "message": message,
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    session.flush()
    return release


def rollback_release(
    session: Session,
    release_key: str,
    *,
    tile_root: Path = Path("/data/tiles/releases"),
) -> DataRelease:
    target = session.scalar(
        select(DataRelease).where(DataRelease.release_key == release_key)
    )
    if target is None or target.status != "superseded":
        raise ReleaseStateError("rollback target must be a retained superseded release")
    previous = session.scalar(
        select(DataRelease)
        .where(DataRelease.status == "superseded")
        .order_by(DataRelease.activated_at.desc().nullslast(), DataRelease.id.desc())
        .limit(1)
    )
    if previous is None or previous.id != target.id:
        raise ReleaseStateError("rollback target is not the immediate previous release")
    if not target.tile_filename or not target.tile_sha256:
        raise ReleaseStateError("rollback target has no healthy tile artifact")
    if not (tile_root / target.tile_filename).is_file():
        raise ReleaseStateError("rollback target tile artifact is missing")
    target.status = "validated"
    session.flush()
    return activate_release(session, target.id)
