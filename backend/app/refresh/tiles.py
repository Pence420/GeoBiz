import hashlib
import json
from pathlib import Path
import re
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

RELEASE_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PMTILES_MAGIC = b"PMTiles"
PMTILES_VERSION = 3
REPRESENTATIVE_TILES = ((7, 101, 66), (10, 815, 529), (14, 13052, 8474))


class TileVerificationError(ValueError):
    pass


class TileArtifact(BaseModel):
    filename: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    byte_size: int = Field(gt=0)


class TileServiceVerification(BaseModel):
    catalog_visible: bool
    checked_tiles: int = Field(ge=0)


def verify_pmtiles(path: Path, release_key: str) -> TileArtifact:
    if not RELEASE_KEY_PATTERN.fullmatch(release_key):
        raise TileVerificationError("release key must contain lowercase letters, digits, and hyphens")
    if path.name != f"{release_key}.pmtiles":
        raise TileVerificationError("PMTiles filename must match the immutable release key")
    if path.suffix != ".pmtiles" or path.name.endswith(".partial"):
        raise TileVerificationError("partial or non-PMTiles artifacts cannot be activated")
    if not path.is_file() or path.stat().st_size == 0:
        raise TileVerificationError("PMTiles artifact is missing or empty")

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        header = handle.read(8)
        if header[:7] != PMTILES_MAGIC or len(header) != 8:
            raise TileVerificationError("artifact does not contain a PMTiles header")
        if header[7] != PMTILES_VERSION:
            raise TileVerificationError(
                f"unsupported PMTiles version {header[7]}; expected {PMTILES_VERSION}"
            )
        digest.update(header)
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return TileArtifact(
        filename=path.name,
        sha256=digest.hexdigest(),
        byte_size=path.stat().st_size,
    )


def verify_tile_service(
    base_url: str,
    release_key: str,
    *,
    opener: Callable = urlopen,
    timeout_seconds: float = 10,
) -> TileServiceVerification:
    if not RELEASE_KEY_PATTERN.fullmatch(release_key):
        raise TileVerificationError("invalid release key")
    root = base_url.rstrip("/")
    try:
        with opener(Request(f"{root}/catalog"), timeout=timeout_seconds) as response:
            catalog_bytes = response.read()
        catalog = json.loads(catalog_bytes)
        if release_key not in json.dumps(catalog, separators=(",", ":")):
            raise TileVerificationError("release is not visible in the tile catalog")
        checked = 0
        for zoom, x, y in REPRESENTATIVE_TILES:
            url = f"{root}/{release_key}/{zoom}/{x}/{y}"
            with opener(Request(url), timeout=timeout_seconds) as response:
                if not response.read():
                    raise TileVerificationError(f"representative tile is empty: {url}")
            checked += 1
        return TileServiceVerification(catalog_visible=True, checked_tiles=checked)
    except TileVerificationError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise TileVerificationError(f"tile service verification failed: {error}") from error
