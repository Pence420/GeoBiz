from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.scoring.domain import ScoreResult


class AnalyzeLocationRequest(BaseModel):
    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]
    business_category: Literal["restaurant", "gym", "pharmacy"]
    radius_m: Literal[500, 1000, 2000, 3000, 5000] = 1000


class ContainingArea(BaseModel):
    id: int
    name: str
    official_code: str | None
    coverage_official_code: str | None = None
    population_density: float | None


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
    business_category: Literal["restaurant", "gym", "pharmacy"]
    radius_m: int
    containing_area: ContainingArea
    nearby_metrics: NearbyMetrics
    score: ScoreResult
    dataset_fingerprint: str
    limitations: list[str]
