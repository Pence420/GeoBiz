from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import os
from pathlib import Path
import tempfile
from typing import Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.imports.manifest import sha256_file
from app.refresh.config import SourceConfig

CHUNK_SIZE = 1024 * 1024


class DownloadError(RuntimeError):
    pass


class DownloadSecurityError(DownloadError):
    pass


class SafeRedirectHandler(HTTPRedirectHandler):
    def __init__(self, allowed_hosts: frozenset[str]) -> None:
        super().__init__()
        self.allowed_hosts = allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        host = (urlparse(newurl).hostname or "").lower()
        if host not in self.allowed_hosts:
            raise DownloadSecurityError(f"redirect host {host!r} is not allow-listed")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrlOpener(Protocol):
    def open(self, request: Request, *, timeout: float): ...


@dataclass(frozen=True)
class DownloadResult:
    status: Literal["downloaded", "unchanged"]
    path: Path
    sha256: str
    byte_size: int
    retrieved_at: datetime
    etag: str | None = None
    last_modified: str | None = None


def download_source(
    source: SourceConfig,
    destination_dir: Path,
    *,
    opener: UrlOpener | None = None,
    timeout_seconds: float = 30,
    previous_etag: str | None = None,
    previous_last_modified: str | None = None,
) -> DownloadResult:
    source_host = (source.url.host or "").lower()
    allowed_hosts = frozenset(host.lower() for host in source.allowed_hosts)
    if source_host not in allowed_hosts:
        raise DownloadSecurityError("source URL host is not allow-listed")

    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source.filename
    request_headers = {"User-Agent": "GeoBiz/2.0 academic-data-refresh"}
    if previous_etag:
        request_headers["If-None-Match"] = previous_etag
    if previous_last_modified:
        request_headers["If-Modified-Since"] = previous_last_modified
    request = Request(
        str(source.url),
        data=b"" if source.method == "POST" else None,
        headers=request_headers,
        method=source.method,
    )
    opener = opener or build_opener(SafeRedirectHandler(allowed_hosts))

    partial_path: Path | None = None
    try:
        try:
            response = opener.open(request, timeout=timeout_seconds)
        except HTTPError as error:
            if error.code == 304:
                if not destination.is_file() or destination.stat().st_size == 0:
                    raise DownloadError("source returned 304 but no local snapshot exists")
                return DownloadResult(
                    status="unchanged",
                    path=destination,
                    sha256=sha256_file(destination),
                    byte_size=destination.stat().st_size,
                    retrieved_at=datetime.now(UTC),
                    etag=previous_etag,
                    last_modified=previous_last_modified,
                )
            raise

        with response:
            final_url = getattr(response, "url", str(source.url))
            final_host = (urlparse(final_url).hostname or "").lower()
            if final_host not in allowed_hosts:
                raise DownloadSecurityError(
                    f"response host {final_host!r} is not allow-listed"
                )
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=destination_dir,
                prefix=f".{source.filename}.",
                suffix=".partial",
                delete=False,
            ) as output:
                partial_path = Path(output.name)
                digest = hashlib.sha256()
                byte_size = 0
                while chunk := response.read(CHUNK_SIZE):
                    byte_size += len(chunk)
                    if byte_size > source.max_bytes:
                        raise DownloadError(
                            f"download exceeds {source.max_bytes} byte limit"
                        )
                    digest.update(chunk)
                    output.write(chunk)
                if byte_size == 0:
                    raise DownloadError("downloaded source is empty")
                output.flush()
                os.fsync(output.fileno())
            os.replace(partial_path, destination)
            partial_path = None
            headers = getattr(response, "headers", {})
            return DownloadResult(
                status="downloaded",
                path=destination,
                sha256=digest.hexdigest(),
                byte_size=byte_size,
                retrieved_at=datetime.now(UTC),
                etag=headers.get("ETag"),
                last_modified=headers.get("Last-Modified"),
            )
    except DownloadError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise DownloadError(f"failed to download {source.dataset_slug}: {error}") from error
    finally:
        if partial_path is not None:
            partial_path.unlink(missing_ok=True)
