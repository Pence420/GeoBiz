import hashlib
import json
from datetime import UTC, datetime

import pytest

from app.imports.contracts import ImportManifest
from app.imports.manifest import ManifestChecksumError, load_verified_manifest


def _write_manifest(tmp_path, checksum: str):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "dataset_slug": "osm-dki-businesses",
                "source_name": "OpenStreetMap Jakarta extract",
                "source_url": "https://download.openstreetmap.fr/example.osm.pbf",
                "source_license": "ODbL 1.0",
                "source_observed_at": "2026-09-29",
                "retrieved_at": datetime.now(UTC).isoformat(),
                "sha256": checksum,
                "local_filename": "snapshot.json",
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def test_load_verified_manifest_accepts_matching_file(tmp_path) -> None:
    raw_path = tmp_path / "snapshot.json"
    raw_path.write_text('{"source":"real"}', encoding="utf-8")
    digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()

    manifest = load_verified_manifest(_write_manifest(tmp_path, digest), raw_path)

    assert isinstance(manifest, ImportManifest)
    assert manifest.sha256 == digest


def test_load_verified_manifest_rejects_changed_file(tmp_path) -> None:
    raw_path = tmp_path / "snapshot.json"
    raw_path.write_text("changed", encoding="utf-8")

    with pytest.raises(ManifestChecksumError, match="checksum"):
        load_verified_manifest(_write_manifest(tmp_path, "0" * 64), raw_path)
