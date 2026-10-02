from datetime import date
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, model_validator


class SourceConfig(BaseModel):
    role: str
    dataset_slug: str
    source_name: str
    url: HttpUrl
    allowed_hosts: list[str] = Field(min_length=1)
    license_name: str
    filename: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    max_bytes: int = Field(gt=0)
    observed_at: date | None = None
    request_parameters: dict[str, Any] | None = None

    @model_validator(mode="after")
    def source_host_is_allowed(self) -> "SourceConfig":
        if self.url.host not in self.allowed_hosts:
            raise ValueError("source URL host must appear in allowed_hosts")
        return self


class RefreshConfig(BaseModel):
    taxonomy_version: str = "v2.0.0"
    scoring_version: str = "v2.0.0"
    minimum_free_bytes: int = Field(default=2_000_000_000, ge=0)
    workspace_root: Path = Path("/data/refresh")
    tile_root: Path = Path("/data/tiles/releases")
    aliases_path: Path = Path("/data/crosswalks/dki_kelurahan_aliases.csv")
    sources: list[SourceConfig] = Field(min_length=1)

    @classmethod
    def load(cls, path: Path) -> "RefreshConfig":
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))
