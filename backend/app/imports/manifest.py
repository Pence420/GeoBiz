import hashlib
from pathlib import Path

from app.imports.contracts import ImportManifest


class ManifestChecksumError(ValueError):
    pass


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_verified_manifest(manifest_path: Path, raw_path: Path) -> ImportManifest:
    manifest = ImportManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    if manifest.local_filename != raw_path.name:
        raise ManifestChecksumError(
            f"manifest expects {manifest.local_filename!r}, got {raw_path.name!r}"
        )
    actual_checksum = sha256_file(raw_path)
    if actual_checksum != manifest.sha256:
        raise ManifestChecksumError(
            "raw file checksum does not match the committed manifest"
        )
    return manifest
