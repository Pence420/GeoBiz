from datetime import date
from typing import Annotated, Literal

from pydantic import AliasChoices, BaseModel, Field

from app.scoring.domain import ScoreResult
from app.datasets.service import DatasetSnapshot

BusinessCategorySlug = Literal[
    "restaurant", "gym", "pharmacy", "fnb", "retail", "services"
]


class AnalyzeLocationRequest(BaseModel):
    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]
    business_category: BusinessCategorySlug
    radius_m: Literal[500, 1000, 2000, 3000, 5000] = Field(
        default=1000,
        validation_alias=AliasChoices("radius_m", "radius"),
    )


class ContainingArea(BaseModel):
    id: int
    name: str
    official_code: str | None
    coverage_official_code: str | None = None
    population_density: float | None
    area_type: str | None = None
    kecamatan: str | None = None
    population: int | None = None
    population_observed_at: date | None = None


class NearbyBusiness(BaseModel):
    name: str | None
    business_subtype: str
    distance_m: float = Field(ge=0)
    latitude: float
    longitude: float
    source_type: str
    source_record_id: str
    address: str | None = None
    brand: str | None = None
    operator: str | None = None
    opening_hours: str | None = None
    phone: str | None = None
    website: str | None = None


class NearbyTransport(BaseModel):
    name: str
    transport_type: str
    distance_m: float = Field(ge=0)
    latitude: float
    longitude: float
    source_record_id: str


class NearbyRoad(BaseModel):
    name: str | None
    road_type: str
    distance_m: float = Field(ge=0)
    source_type: str
    source_record_id: str


class PoiBreakdown(BaseModel):
    commercial: dict[str, int]
    office: dict[str, int]
    education: dict[str, int]
    healthcare: dict[str, int]


class AnalysisCoverage(BaseModel):
    total_businesses: int = Field(ge=0)
    named_business_percent: float = Field(ge=0, le=100)
    missing_source_fields: dict[str, int]


class LocationEvidence(BaseModel):
    competitor_subtype_counts: dict[str, int]
    nearest_competitors: list[NearbyBusiness]
    nearest_transport: NearbyTransport | None
    nearest_major_road: NearbyRoad | None
    poi_breakdown: PoiBreakdown
    coverage: AnalysisCoverage


class NearbyMetrics(BaseModel):
    competitor_count: int
    transport_stop_count: int | None
    commercial_poi_count: int | None
    office_count: int | None
    university_count: int | None
    healthcare_count: int | None
    population_density: float | None
    nearest_major_road_m: float | None


class AnalyzeLocationResponse(BaseModel):
    latitude: float
    longitude: float
    business_category: BusinessCategorySlug
    radius_m: int
    containing_area: ContainingArea
    nearby_metrics: NearbyMetrics
    score: ScoreResult
    dataset_fingerprint: str
    taxonomy_version: str
    scoring_version: str
    competitor_subtype_counts: dict[str, int]
    nearest_competitors: list[NearbyBusiness]
    nearest_transport: NearbyTransport | None
    nearest_major_road: NearbyRoad | None
    poi_breakdown: PoiBreakdown
    coverage: AnalysisCoverage
    source_snapshots: list[DatasetSnapshot]
    limitations: list[str]
