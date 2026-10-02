from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ReleaseSummary(BaseModel):
    id: int
    release_key: str
    status: str
    dataset_fingerprint: str
    taxonomy_version: str
    scoring_version: str
    tile_filename: str | None
    tile_sha256: str | None
    created_at: datetime
    validated_at: datetime | None
    activated_at: datetime | None
    failure: dict[str, object] | None


class RefreshStatusResponse(BaseModel):
    active: ReleaseSummary
    pending: ReleaseSummary | None
    latest_failed: ReleaseSummary | None


class MapConfig(BaseModel):
    release_id: int
    release_key: str
    taxonomy_version: str
    tile_url: str | None
    tile_sha256: str | None
    bounds: tuple[float, float, float, float]
    min_zoom: int
    max_zoom: int
    attribution: str
    mode: Literal["offline", "online_fallback"]
    fallback_available: bool
