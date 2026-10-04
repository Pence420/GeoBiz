import hashlib
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from app.refresh.config import SourceConfig
from app.refresh.downloader import (
    DownloadError,
    DownloadSecurityError,
    SafeRedirectHandler,
    download_source,
)


class FakeResponse:
    def __init__(self, body: bytes, *, url: str, headers: dict[str, str] | None = None):
        self._stream = BytesIO(body)
        self.url = url
        self.headers = headers or {}
        self.status = 200

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class FakeOpener:
    def __init__(self, result):
        self.result = result
        self.request: Request | None = None
        self.timeout: float | None = None

    def open(self, request: Request, *, timeout: float):
        self.request = request
        self.timeout = timeout
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _source(**overrides) -> SourceConfig:
    values = {
        "role": "osm",
        "dataset_slug": "osm-jakarta",
        "source_name": "OpenStreetMap Jakarta",
        "url": "https://download.openstreetmap.fr/jakarta.osm.pbf",
        "allowed_hosts": ["download.openstreetmap.fr"],
        "license_name": "ODbL-1.0",
        "filename": "jakarta.osm.pbf",
        "max_bytes": 1024,
    }
    values.update(overrides)
    return SourceConfig(**values)


def test_download_streams_sha256_and_atomically_publishes(tmp_path: Path) -> None:
    body = b"real source bytes"
    opener = FakeOpener(
        FakeResponse(
            body,
            url="https://download.openstreetmap.fr/jakarta.osm.pbf",
            headers={"ETag": '"abc"', "Last-Modified": "Wed, 01 Oct 2026 00:00:00 GMT"},
        )
    )

    result = download_source(_source(), tmp_path, opener=opener, timeout_seconds=7)

    assert result.status == "downloaded"
    assert result.path == tmp_path / "jakarta.osm.pbf"
    assert result.path.read_bytes() == body
    assert result.sha256 == hashlib.sha256(body).hexdigest()
    assert result.byte_size == len(body)
    assert result.etag == '"abc"'
    assert opener.timeout == 7
    assert not list(tmp_path.glob("*.partial"))


def test_download_rejects_cross_host_redirect() -> None:
    handler = SafeRedirectHandler(frozenset({"download.openstreetmap.fr"}))
    request = Request("https://download.openstreetmap.fr/jakarta.osm.pbf")

    with pytest.raises(DownloadSecurityError):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://attacker.example/jakarta.osm.pbf",
        )


@pytest.mark.parametrize("body,max_bytes", [(b"", 10), (b"too-large", 3)])
def test_download_rejects_empty_or_oversized_and_removes_partial(
    tmp_path: Path, body: bytes, max_bytes: int
) -> None:
    opener = FakeOpener(FakeResponse(body, url=str(_source().url)))

    with pytest.raises(DownloadError):
        download_source(_source(max_bytes=max_bytes), tmp_path, opener=opener)

    assert not (tmp_path / "jakarta.osm.pbf").exists()
    assert not list(tmp_path.glob("*.partial"))


def test_download_304_returns_unchanged_and_sends_conditionals(tmp_path: Path) -> None:
    destination = tmp_path / "jakarta.osm.pbf"
    destination.write_bytes(b"existing")
    error = HTTPError(str(_source().url), 304, "Not Modified", {}, None)
    opener = FakeOpener(error)

    result = download_source(
        _source(),
        tmp_path,
        opener=opener,
        previous_etag='"previous"',
        previous_last_modified="Tue, 30 Sep 2026 00:00:00 GMT",
    )

    assert result.status == "unchanged"
    assert result.path == destination
    assert result.sha256 == hashlib.sha256(b"existing").hexdigest()
    assert opener.request is not None
    assert opener.request.get_header("If-none-match") == '"previous"'
    assert opener.request.get_header("If-modified-since") == "Tue, 30 Sep 2026 00:00:00 GMT"


def test_source_host_must_be_allow_listed() -> None:
    with pytest.raises(ValueError, match="allowed_hosts"):
        _source(allowed_hosts=["example.com"])


def test_download_can_use_post_for_read_only_public_api(tmp_path: Path) -> None:
    opener = FakeOpener(FakeResponse(b'{"success":true}', url=str(_source().url)))

    download_source(_source(method="POST"), tmp_path, opener=opener)

    assert opener.request is not None
    assert opener.request.get_method() == "POST"
    assert opener.request.data == b""
