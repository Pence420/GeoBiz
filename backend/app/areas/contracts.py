from typing import Literal

from pydantic import BaseModel, Field


class AreaRankingItem(BaseModel):
    area_id: int
    area_name: str
    rank: int = Field(ge=1)
    final_score: float = Field(ge=0, le=100)
    label: Literal["Very Low", "Low", "Moderate", "Good", "High"]
    longitude: float
    latitude: float
    normalized_factors: dict[str, float | None]
    raw_factors: dict[str, float | None]
    representative_method: Literal["point_on_surface"]


class AreaRankingResponse(BaseModel):
    business_category: Literal["restaurant", "gym", "pharmacy"]
    radius_m: int
    scoring_version: str
    dataset_fingerprint: str
    items: list[AreaRankingItem]

