from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.taxonomy.businesses import BusinessCategorySlug


class CategoryCount(BaseModel):
    category: BusinessCategorySlug
    count: int = Field(ge=0)


class SubtypeCount(BaseModel):
    subtype: str
    count: int = Field(ge=0)


class OpportunitySummary(BaseModel):
    area_id: int
    area_name: str
    final_score: float = Field(ge=0, le=100)
    label: str


class ScoreBand(BaseModel):
    label: str
    minimum: int
    maximum: int
    area_count: int = Field(ge=0)


class PopulationCompetitionPoint(BaseModel):
    area_name: str
    population_density: float
    competitor_count: float
    final_score: float = Field(ge=0, le=100)


class CoverageMetric(BaseModel):
    key: str
    label: str
    value: float
    unit: str
    definition: str


class AnalyticsResponse(BaseModel):
    business_category: BusinessCategorySlug
    radius_m: int
    release_key: str
    taxonomy_version: str
    scoring_version: str
    dataset_fingerprint: str
    category_counts: list[CategoryCount]
    subtype_counts: list[SubtypeCount]
    top_opportunities: list[OpportunitySummary]
    score_distribution: list[ScoreBand]
    population_competition: list[PopulationCompetitionPoint]
    coverage: list[CoverageMetric]


class MethodologyDataset(BaseModel):
    slug: str
    provider: str
    source_url: str
    license_name: str
    attribution: str
    observed_at: date | None
    retrieved_at: datetime
    sha256: str


class TaxonomyRule(BaseModel):
    category: BusinessCategorySlug
    subtype: str
    required_tags: dict[str, str]


class CategoryMethodology(BaseModel):
    category: BusinessCategorySlug
    weights: dict[str, float]


class MethodologyResponse(BaseModel):
    coverage: str
    release_key: str
    taxonomy_version: str
    scoring_version: str
    dataset_fingerprint: str
    tile_sha256: str | None
    supported_radii_m: list[int]
    representative_area_method: str
    normalization: str
    factor_definitions: dict[str, str]
    categories: list[CategoryMethodology]
    taxonomy_rules: list[TaxonomyRule]
    datasets: list[MethodologyDataset]
    limitations: list[str]


class SearchResult(BaseModel):
    id: str
    name: str
    result_type: Literal["coordinate", "area", "business", "landmark"]
    subtitle: str
    longitude: float
    latitude: float
    source_record_id: str | None = None
