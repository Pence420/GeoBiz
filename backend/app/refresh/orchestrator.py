from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.datasets.service import active_release
from app.db.models import DataRelease
from app.db.models import AdministrativeArea, Business, BusinessCategory, Poi, Road, TransportStop
from app.imports.administrative import boundary_geometry
from app.imports.contracts import ImportManifest
from app.imports.gtfs import filter_gtfs_to_boundary, parse_gtfs_stops
from app.imports.promotion import (
    promote_dki_boundary,
    promote_gtfs_stops,
    promote_osm_context,
    promote_osm_records,
    promote_population_areas,
)
from app.imports.staging import stage_osm_context, stage_osm_pbf, stage_population_areas
from app.refresh.downloader import download_source
from app.refresh.config import RefreshConfig
from app.releases.service import activate_release, create_staging_release, fail_release

RELEASE_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EXPECTED_OPPORTUNITY_SCORES = 267 * 3 * 5


class RefreshBusyError(RuntimeError):
    pass


class RefreshStateError(RuntimeError):
    pass


class PreparedInputs(BaseModel):
    dataset_fingerprint: str
    combined_manifest: dict
    verified_pbf_path: Path
    boundary_path: Path
    staged: dict[str, Any] = Field(default_factory=dict, exclude=True)


class PreparedRelease(BaseModel):
    release_key: str
    status: Literal["dry-run", "unchanged", "validated", "failed"]
    workspace: str | None = None
    verified_pbf_path: str | None = None
    boundary_path: str | None = None
    expected_tile_path: str | None = None
    failure: dict | None = None


class TileMetadata(BaseModel):
    filename: str
    sha256: str
    byte_size: int


@dataclass
class RefreshHooks:
    download: Callable[[RefreshConfig, Path, DataRelease], PreparedInputs]
    validate: Callable[[PreparedInputs, bool], None]
    promote: Callable[[Session, int, PreparedInputs], None]
    verify_tile: Callable[[Path, str], TileMetadata]
    derive: Callable[[Session, int, str], int]


LockFunction = Callable[[Session], bool]
UnlockFunction = Callable[[Session], None]


def _acquire_advisory_lock(session: Session) -> bool:
    return bool(
        session.scalar(
            text("SELECT pg_try_advisory_lock(hashtext('geobiz-refresh'))")
        )
    )


def _release_advisory_lock(session: Session) -> None:
    session.scalar(text("SELECT pg_advisory_unlock(hashtext('geobiz-refresh'))"))


class RefreshOrchestrator:
    def __init__(
        self,
        config: RefreshConfig,
        hooks: RefreshHooks,
        *,
        lock: LockFunction = _acquire_advisory_lock,
        unlock: UnlockFunction = _release_advisory_lock,
    ) -> None:
        self.config = config
        self.hooks = hooks
        self.lock = lock
        self.unlock = unlock

    def prepare(
        self,
        session: Session,
        *,
        release_key: str,
        dry_run: bool,
        accept_count_change: bool,
    ) -> PreparedRelease:
        self._validate_release_key(release_key)
        if not self.lock(session):
            raise RefreshBusyError("another GeoBiz refresh phase is running")
        workspace: Path | None = None
        release: DataRelease | None = None
        try:
            self._preflight()
            pending = session.scalar(
                select(DataRelease).where(
                    DataRelease.status.in_(("staging", "validated"))
                )
            )
            if pending is not None:
                raise RefreshStateError(
                    f"release {pending.release_key} is already being prepared"
                )

            if dry_run:
                with tempfile.TemporaryDirectory(
                    prefix=f"{release_key}-", dir=self.config.workspace_root
                ) as temporary:
                    inputs = self.hooks.download(
                        self.config, Path(temporary), active_release(session)
                    )
                    self.hooks.validate(inputs, accept_count_change)
                    self._validate_count_changes(
                        session,
                        inputs,
                        accept_count_change=accept_count_change,
                    )
                    return self._prepared_result(
                        release_key, "dry-run", Path(temporary), inputs
                    )

            workspace = self.config.workspace_root / release_key
            if workspace.exists():
                raise RefreshStateError("release workspace already exists")
            workspace.mkdir(parents=True)
            inputs = self.hooks.download(
                self.config, workspace, active_release(session)
            )
            self.hooks.validate(inputs, accept_count_change)
            self._validate_count_changes(
                session, inputs, accept_count_change=accept_count_change
            )
            if inputs.dataset_fingerprint == active_release(session).dataset_fingerprint:
                shutil.rmtree(workspace)
                return self._prepared_result(
                    release_key, "unchanged", None, inputs
                )

            expected_tile = self.config.tile_root / f"{release_key}.pmtiles"
            manifest = {
                **inputs.combined_manifest,
                "release_key": release_key,
                "dataset_fingerprint": inputs.dataset_fingerprint,
                "taxonomy_version": self.config.taxonomy_version,
                "scoring_version": self.config.scoring_version,
                "workspace_path": str(workspace),
                "verified_pbf_path": str(inputs.verified_pbf_path),
                "boundary_path": str(inputs.boundary_path),
                "expected_tile_path": str(expected_tile),
            }
            release = create_staging_release(
                session,
                {
                    "release_key": release_key,
                    "dataset_fingerprint": inputs.dataset_fingerprint,
                    "taxonomy_version": self.config.taxonomy_version,
                    "scoring_version": self.config.scoring_version,
                    **manifest,
                },
            )
            with session.begin_nested():
                self.hooks.promote(session, release.id, inputs)
            release.status = "validated"
            release.validated_at = datetime.now(UTC)
            release.combined_manifest = manifest
            session.flush()
            return self._prepared_result(
                release_key, "validated", workspace, inputs, expected_tile
            )
        except RefreshStateError:
            raise
        except Exception as error:
            if dry_run:
                return PreparedRelease(
                    release_key=release_key,
                    status="failed",
                    failure={"phase": "prepare", "message": str(error)},
                )
            if release is None:
                release = create_staging_release(
                    session,
                    {
                        "release_key": release_key,
                        "dataset_fingerprint": "0" * 64,
                        "taxonomy_version": self.config.taxonomy_version,
                        "scoring_version": self.config.scoring_version,
                    },
                )
            fail_release(session, release.id, phase="prepare", message=str(error))
            return PreparedRelease(
                release_key=release_key,
                status="failed",
                workspace=str(workspace) if workspace else None,
                failure=release.failure,
            )
        finally:
            self.unlock(session)

    def activate(
        self,
        session: Session,
        *,
        release_key: str,
        tile_path: Path,
    ) -> DataRelease:
        self._validate_release_key(release_key)
        if not self.lock(session):
            raise RefreshBusyError("another GeoBiz refresh phase is running")
        release: DataRelease | None = None
        try:
            release = session.scalar(
                select(DataRelease).where(DataRelease.release_key == release_key)
            )
            if release is None or release.status != "validated":
                raise RefreshStateError("activation requires a validated release")
            expected = Path(str(release.combined_manifest["expected_tile_path"]))
            if tile_path.resolve() != expected.resolve():
                raise RefreshStateError("tile path is not the prepared immutable path")
            tile = self.hooks.verify_tile(tile_path, release_key)
            try:
                with session.begin_nested():
                    generated = self.hooks.derive(
                        session, release.id, release.scoring_version
                    )
                    if generated != EXPECTED_OPPORTUNITY_SCORES:
                        raise ValueError(
                            f"expected {EXPECTED_OPPORTUNITY_SCORES} opportunity scores, "
                            f"got {generated}"
                        )
                    release.tile_filename = tile.filename
                    release.tile_sha256 = tile.sha256
                    session.flush()
                    activate_release(session, release.id)
            except Exception as error:
                session.refresh(release)
                fail_release(session, release.id, phase="activate", message=str(error))
            return release
        except RefreshStateError:
            raise
        except Exception as error:
            if release is not None and release.status == "validated":
                fail_release(
                    session, release.id, phase="tile_verification", message=str(error)
                )
                return release
            raise
        finally:
            self.unlock(session)

    def _preflight(self) -> None:
        self.config.workspace_root.mkdir(parents=True, exist_ok=True)
        self.config.tile_root.mkdir(parents=True, exist_ok=True)
        if not self.config.aliases_path.is_file():
            raise RefreshStateError("configured population aliases file is missing")
        free_bytes = shutil.disk_usage(self.config.workspace_root).free
        if free_bytes < self.config.minimum_free_bytes:
            raise RefreshStateError("insufficient free disk space for refresh")
        if not os.access(self.config.workspace_root, os.W_OK):
            raise RefreshStateError("refresh workspace is not writable")
        if not os.access(self.config.tile_root, os.W_OK):
            raise RefreshStateError("tile release directory is not writable")

    def _validate_count_changes(
        self,
        session: Session,
        inputs: PreparedInputs,
        *,
        accept_count_change: bool,
    ) -> None:
        new_counts = inputs.staged.get("counts")
        if not new_counts or accept_count_change:
            return
        release_id = active_release(session).id
        previous = dict(
            session.execute(
                select(BusinessCategory.slug, func.count(Business.id))
                .join(Business, Business.category_id == BusinessCategory.id)
                .where(Business.data_release_id == release_id)
                .group_by(BusinessCategory.slug)
            ).all()
        )
        previous.update(
            {
                "transport_stops": session.scalar(
                    select(func.count(TransportStop.id)).where(
                        TransportStop.data_release_id == release_id
                    )
                ),
                "pois": session.scalar(
                    select(func.count(Poi.id)).where(Poi.data_release_id == release_id)
                ),
                "roads": session.scalar(
                    select(func.count(Road.id)).where(Road.data_release_id == release_id)
                ),
                "populated_areas": session.scalar(
                    select(func.count(AdministrativeArea.id)).where(
                        AdministrativeArea.data_release_id == release_id,
                        AdministrativeArea.area_type == "kelurahan",
                        AdministrativeArea.population_density.is_not(None),
                    )
                ),
            }
        )
        large_changes = []
        for key, new_count in new_counts.items():
            old_count = int(previous.get(key) or 0)
            if old_count and (new_count < old_count * 0.7 or new_count > old_count * 2):
                large_changes.append(f"{key}: {old_count} -> {new_count}")
        if large_changes:
            raise ValueError(
                "source counts exceed the 30% decrease/100% increase gate; "
                "rerun with --accept-count-change after review: "
                + "; ".join(large_changes)
            )

    def _prepared_result(
        self,
        release_key: str,
        status: Literal["dry-run", "unchanged", "validated"],
        workspace: Path | None,
        inputs: PreparedInputs,
        expected_tile: Path | None = None,
    ) -> PreparedRelease:
        return PreparedRelease(
            release_key=release_key,
            status=status,
            workspace=str(workspace) if workspace else None,
            verified_pbf_path=str(inputs.verified_pbf_path),
            boundary_path=str(inputs.boundary_path),
            expected_tile_path=str(expected_tile) if expected_tile else None,
        )

    @staticmethod
    def _validate_release_key(release_key: str) -> None:
        if not RELEASE_KEY_PATTERN.fullmatch(release_key):
            raise ValueError("release key must contain lowercase letters, digits, and hyphens")


def build_default_hooks() -> RefreshHooks:
    return RefreshHooks(
        download=_download_configured_sources,
        validate=_stage_and_validate_sources,
        promote=_promote_staged_sources,
        verify_tile=_verify_tile,
        derive=_derive_release,
    )


def _download_configured_sources(
    config: RefreshConfig,
    workspace: Path,
    _active: DataRelease,
) -> PreparedInputs:
    raw_dir = workspace / "raw"
    manifest_dir = workspace / "manifests"
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    source_entries = []
    paths: dict[str, Path] = {}
    manifests: dict[str, Path] = {}
    for source in config.sources:
        result = download_source(source, raw_dir)
        manifest = ImportManifest(
            dataset_slug=source.dataset_slug,
            source_name=source.source_name,
            source_url=source.url,
            source_license=source.license_name,
            source_observed_at=source.observed_at,
            retrieved_at=result.retrieved_at,
            sha256=result.sha256,
            local_filename=source.filename,
            request_parameters=source.request_parameters,
        )
        manifest_path = manifest_dir / f"{source.role}.json"
        manifest_path.write_text(
            manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        paths[source.role] = result.path
        manifests[source.role] = manifest_path
        source_entries.append(
            {
                **manifest.model_dump(mode="json"),
                "role": source.role,
                "byte_size": result.byte_size,
                "etag": result.etag,
                "last_modified": result.last_modified,
            }
        )
    fingerprint_payload = [
        (entry["role"], entry["dataset_slug"], entry["sha256"])
        for entry in sorted(source_entries, key=lambda item: item["role"])
    ]
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, separators=(",", ":")).encode()
    ).hexdigest()
    required = {"osm", "boundary", "gtfs", "population"}
    missing = required - paths.keys()
    if missing:
        raise ValueError("refresh configuration is missing roles: " + ", ".join(sorted(missing)))
    return PreparedInputs(
        dataset_fingerprint=fingerprint,
        combined_manifest={"sources": source_entries},
        verified_pbf_path=paths["osm"],
        boundary_path=paths["boundary"],
        staged={"paths": paths, "manifests": manifests, "config": config},
    )


def _stage_and_validate_sources(
    inputs: PreparedInputs,
    _accept_count_change: bool,
) -> None:
    paths = inputs.staged["paths"]
    manifests = inputs.staged["manifests"]
    config: RefreshConfig = inputs.staged["config"]
    osm_manifest, businesses = stage_osm_pbf(
        paths["osm"], manifests["osm"], paths["boundary"], manifests["boundary"]
    )
    context_manifest, pois, roads, context_report = stage_osm_context(
        paths["osm"], manifests["osm"], paths["boundary"], manifests["boundary"]
    )
    geometry = boundary_geometry(
        json.loads(paths["boundary"].read_text(encoding="utf-8"))
    )
    gtfs_records, gtfs_report = filter_gtfs_to_boundary(
        parse_gtfs_stops(paths["gtfs"]), geometry
    )
    population_manifest, geometry_manifest, areas, population_report = (
        stage_population_areas(
            paths["population"],
            manifests["population"],
            paths["osm"],
            manifests["osm"],
            paths["boundary"],
            manifests["boundary"],
            config.aliases_path,
        )
    )
    inputs.staged.update(
        {
            "osm_manifest": osm_manifest,
            "businesses": businesses,
            "context_manifest": context_manifest,
            "pois": pois,
            "roads": roads,
            "context_report": context_report,
            "gtfs_manifest": ImportManifest.model_validate_json(
                manifests["gtfs"].read_text(encoding="utf-8")
            ),
            "gtfs_records": gtfs_records,
            "gtfs_report": gtfs_report,
            "population_manifest": population_manifest,
            "geometry_manifest": geometry_manifest,
            "areas": areas,
            "population_report": population_report,
            "boundary_manifest": ImportManifest.model_validate_json(
                manifests["boundary"].read_text(encoding="utf-8")
            ),
            "boundary_payload": json.loads(
                paths["boundary"].read_text(encoding="utf-8")
            ),
            "counts": {
                **businesses.quality_report.category_counts,
                "transport_stops": len(gtfs_records),
                "pois": len(pois),
                "roads": len(roads),
                "populated_areas": len(areas),
            },
        }
    )
    inputs.combined_manifest["quality_counts"] = inputs.staged["counts"]


def _promote_staged_sources(
    session: Session,
    release_id: int,
    inputs: PreparedInputs,
) -> None:
    staged = inputs.staged
    promote_dki_boundary(
        session, release_id, staged["boundary_manifest"], staged["boundary_payload"]
    )
    promote_osm_records(
        session,
        release_id,
        staged["osm_manifest"],
        staged["businesses"].records,
        staged["businesses"].quality_report,
    )
    promote_osm_context(
        session,
        release_id,
        staged["context_manifest"],
        staged["pois"],
        staged["roads"],
        staged["context_report"],
    )
    promote_gtfs_stops(
        session,
        release_id,
        staged["gtfs_manifest"],
        staged["gtfs_records"],
        staged["gtfs_report"],
    )
    promote_population_areas(
        session,
        release_id,
        staged["population_manifest"],
        staged["geometry_manifest"],
        staged["areas"],
        staged["population_report"],
    )


def _verify_tile(path: Path, release_key: str) -> TileMetadata:
    from app.refresh.tiles import verify_pmtiles

    artifact = verify_pmtiles(path, release_key)
    return TileMetadata(**artifact.model_dump())


def _derive_release(session: Session, release_id: int, version: str) -> int:
    from app.areas.generator import generate_opportunity_scores
    from app.scoring.generator import generate_normalization_profiles

    profiles = generate_normalization_profiles(
        session, version=version, release_id=release_id
    )
    if len(profiles) != 15:
        raise ValueError(f"expected 15 normalization profiles, got {len(profiles)}")
    scores = generate_opportunity_scores(session, version=version, release_id=release_id)
    return len(scores)
