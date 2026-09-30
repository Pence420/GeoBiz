from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel


class CategorySummary(BaseModel):
    slug: Literal["restaurant", "gym", "pharmacy"]
    name: str
    description: str | None
    business_count: int


class DatasetSummary(BaseModel):
    slug: str
    provider: str
    source_url: str
    license_name: str
    attribution: str
    observed_at: date | None
    retrieved_at: datetime
    sha256: str


class MetadataResponse(BaseModel):
    coverage: str
    categories: list[str]
    supported_radii_m: list[int]
    dataset_fingerprint: str
    datasets: list[DatasetSummary]


class GeoJsonFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: int
    geometry: dict[str, Any]
    properties: dict[str, Any]


class GeoJsonFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJsonFeature]
    attribution: str = "© OpenStreetMap contributors"


class ApiError(BaseModel):
    code: str
    message: str
