from pathlib import Path
import hashlib

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.datasets.service import active_release
from app.db.models import Business, DataRelease, DataReleaseSource
from app.refresh.config import RefreshConfig, SourceConfig
from app.refresh.orchestrator import (
    PreparedInputs,
    RefreshBusyError,
    RefreshHooks,
    RefreshOrchestrator,
    RefreshStateError,
    TileMetadata,
)


def _config(tmp_path: Path) -> RefreshConfig:
    aliases = tmp_path / "aliases.csv"
    aliases.write_text("source,target\n", encoding="utf-8")
    return RefreshConfig(
        minimum_free_bytes=0,
        workspace_root=tmp_path / "refresh",
        tile_root=tmp_path / "tiles",
        aliases_path=aliases,
        sources=[
            SourceConfig(
                role="osm",
                dataset_slug="osm-test",
                source_name="OSM Test",
                url="https://download.openstreetmap.fr/test.pbf",
                allowed_hosts=["download.openstreetmap.fr"],
                license_name="ODbL-1.0",
                filename="test.pbf",
                max_bytes=100,
            )
        ],
    )


def _hooks(*, fail_at: str | None = None) -> RefreshHooks:
    def download(_config, workspace, _active):
        if fail_at == "download":
            raise RuntimeError("download failed")
        source = workspace / "test.pbf"
        source.write_bytes(b"real")
        return PreparedInputs(
            dataset_fingerprint="d" * 64,
            combined_manifest={"sources": [{"sha256": "d" * 64}]},
            verified_pbf_path=source,
            boundary_path=workspace / "boundary.geojson",
        )

    def validate(_inputs, _accept_count_change):
        if fail_at == "validate":
            raise RuntimeError("validation failed")

    def verify_tile(path, release_key):
        if fail_at == "tile_verification":
            raise RuntimeError("tile failed")
        return TileMetadata(
            filename=path.name,
            sha256="e" * 64,
            byte_size=10,
        )

    def derive(_session, _release_id, _version):
        if fail_at == "derive":
            raise RuntimeError("derive failed")
        return 4005

    return RefreshHooks(
        download=download,
        validate=validate,
        promote=lambda _session, _release_id, _inputs: None,
        verify_tile=verify_tile,
        derive=derive,
    )


@pytest.mark.parametrize("failure_phase", ["download", "validate"])
def test_prepare_failure_keeps_old_release_active(
    db_session: Session, tmp_path: Path, failure_phase: str
) -> None:
    old_release_id = active_release(db_session).id
    orchestrator = RefreshOrchestrator(_config(tmp_path), _hooks(fail_at=failure_phase))

    result = orchestrator.prepare(
        db_session,
        release_key=f"refresh-20261001-{failure_phase.replace('_', '-')}",
        dry_run=False,
        accept_count_change=False,
    )

    assert result.status == "failed"
    assert active_release(db_session).id == old_release_id


@pytest.mark.parametrize("failure_phase", ["tile_verification", "derive"])
def test_activate_failure_keeps_old_release_active(
    db_session: Session, tmp_path: Path, failure_phase: str
) -> None:
    old_release_id = active_release(db_session).id
    orchestrator = RefreshOrchestrator(_config(tmp_path), _hooks())
    prepared = orchestrator.prepare(
        db_session,
        release_key=f"refresh-20261001-{failure_phase.replace('_', '-')}",
        dry_run=False,
        accept_count_change=False,
    )
    tile_path = Path(prepared.expected_tile_path)
    tile_path.parent.mkdir(parents=True, exist_ok=True)
    tile_path.write_bytes(b"PMTiles")
    failing = RefreshOrchestrator(_config(tmp_path), _hooks(fail_at=failure_phase))

    result = failing.activate(
        db_session,
        release_key=prepared.release_key,
        tile_path=tile_path,
    )

    assert result.status == "failed"
    assert active_release(db_session).id == old_release_id


def test_dry_run_and_unchanged_do_not_create_release(
    db_session: Session, tmp_path: Path
) -> None:
    config = _config(tmp_path)
    existing_keys = {
        row.release_key for row in db_session.query(type(active_release(db_session))).all()
    }
    dry_run = RefreshOrchestrator(config, _hooks()).prepare(
        db_session,
        release_key="refresh-20261001-dry",
        dry_run=True,
        accept_count_change=False,
    )
    unchanged_hooks = _hooks()
    active = active_release(db_session)
    unchanged_hooks.download = lambda _config, workspace, _active: PreparedInputs(
        dataset_fingerprint=active.dataset_fingerprint,
        combined_manifest={},
        verified_pbf_path=workspace / "same.pbf",
        boundary_path=workspace / "same.geojson",
    )
    unchanged = RefreshOrchestrator(config, unchanged_hooks).prepare(
        db_session,
        release_key="refresh-20261001-same",
        dry_run=False,
        accept_count_change=False,
    )

    assert dry_run.status == "dry-run"
    assert unchanged.status == "unchanged"
    assert {
        row.release_key for row in db_session.query(type(active_release(db_session))).all()
    } == existing_keys


def test_lock_contention_rejects_phase(db_session: Session, tmp_path: Path) -> None:
    orchestrator = RefreshOrchestrator(
        _config(tmp_path), _hooks(), lock=lambda _session: False
    )

    with pytest.raises(RefreshBusyError):
        orchestrator.prepare(
            db_session,
            release_key="refresh-20261001-busy",
            dry_run=False,
            accept_count_change=False,
        )


def test_offline_map_prepare_clones_active_snapshot_and_verifies_pbf(
    db_session: Session, tmp_path: Path
) -> None:
    active = active_release(db_session)
    source_pbf = tmp_path / "retained-jakarta.osm.pbf"
    source_pbf.write_bytes(b"retained verified osm snapshot")
    digest = hashlib.sha256(source_pbf.read_bytes()).hexdigest()
    active.combined_manifest = {
        "verified_pbf_path": str(source_pbf),
        "sources": [{"role": "osm", "sha256": digest}],
    }
    db_session.flush()
    config = _config(tmp_path)
    orchestrator = RefreshOrchestrator(config, _hooks())
    old_business_count = db_session.scalar(
        select(func.count(Business.id)).where(Business.data_release_id == active.id)
    )

    result = orchestrator.prepare_offline_map(
        db_session, release_key="offline-map-20261002-test"
    )

    cloned = db_session.scalar(
        select(DataRelease).where(DataRelease.release_key == result.release_key)
    )
    assert result.status == "validated"
    assert Path(result.verified_pbf_path).read_bytes() == source_pbf.read_bytes()
    assert cloned is not None
    assert cloned.dataset_fingerprint == active.dataset_fingerprint
    assert cloned.combined_manifest["release_kind"] == "offline-map-only"
    assert db_session.scalar(
        select(func.count(Business.id)).where(Business.data_release_id == cloned.id)
    ) == old_business_count
    assert db_session.scalar(
        select(func.count(DataReleaseSource.data_release_id)).where(
            DataReleaseSource.data_release_id == cloned.id
        )
    ) == db_session.scalar(
        select(func.count(DataReleaseSource.data_release_id)).where(
            DataReleaseSource.data_release_id == active.id
        )
    )


def test_offline_map_prepare_rejects_tampered_retained_pbf(
    db_session: Session, tmp_path: Path
) -> None:
    active = active_release(db_session)
    source_pbf = tmp_path / "tampered.osm.pbf"
    source_pbf.write_bytes(b"tampered")
    active.combined_manifest = {
        "verified_pbf_path": str(source_pbf),
        "sources": [{"role": "osm", "sha256": "0" * 64}],
    }
    db_session.flush()

    with pytest.raises(RefreshStateError, match="checksum"):
        RefreshOrchestrator(_config(tmp_path), _hooks()).prepare_offline_map(
            db_session, release_key="offline-map-20261002-bad"
        )
