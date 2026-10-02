import hashlib
import json
from io import BytesIO
from pathlib import Path

import pytest

from app.refresh.tiles import (
    TileVerificationError,
    verify_pmtiles,
    verify_tile_service,
)


class FakeHttpResponse:
    def __init__(self, payload: bytes, status: int = 200):
        self._stream = BytesIO(payload)
        self.status = status

    def read(self) -> bytes:
        return self._stream.read()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


def test_verify_pmtiles_accepts_immutable_release_artifact(tmp_path: Path) -> None:
    body = b"PMTiles\x03" + b"real vector tile archive"
    path = tmp_path / "refresh-20261001-1.pmtiles"
    path.write_bytes(body)

    artifact = verify_pmtiles(path, "refresh-20261001-1")

    assert artifact.filename == path.name
    assert artifact.byte_size == len(body)
    assert artifact.sha256 == hashlib.sha256(body).hexdigest()


@pytest.mark.parametrize(
    "release_key,filename,body",
    [
        ("../escape", "escape.pmtiles", b"PMTiles\x03x"),
        ("refresh-good", "different.pmtiles", b"PMTiles\x03x"),
        ("refresh-good", "refresh-good.pmtiles.partial", b"PMTiles\x03x"),
        ("refresh-good", "refresh-good.pmtiles", b"not-pmtiles"),
        ("refresh-good", "refresh-good.pmtiles", b""),
    ],
)
def test_verify_pmtiles_rejects_unsafe_or_invalid_artifact(
    tmp_path: Path, release_key: str, filename: str, body: bytes
) -> None:
    path = tmp_path / filename
    path.write_bytes(body)

    with pytest.raises(TileVerificationError):
        verify_pmtiles(path, release_key)


def test_verify_tile_service_checks_catalog_and_representative_tiles() -> None:
    release_key = "refresh-20261001-1"
    responses = {
        "http://tiles:3000/catalog": FakeHttpResponse(
            json.dumps({release_key: {"format": "pmtiles"}}).encode()
        ),
        f"http://tiles:3000/{release_key}/7/101/66": FakeHttpResponse(b"low"),
        f"http://tiles:3000/{release_key}/10/815/529": FakeHttpResponse(b"medium"),
        f"http://tiles:3000/{release_key}/14/13052/8474": FakeHttpResponse(b"high"),
    }

    result = verify_tile_service(
        "http://tiles:3000",
        release_key,
        opener=lambda request, timeout: responses[request.full_url],
    )

    assert result.catalog_visible is True
    assert result.checked_tiles == 3
