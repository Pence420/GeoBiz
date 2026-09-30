from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field, HttpUrl

NonNegativeInt = Annotated[int, Field(ge=0)]


class SourceIdentity(BaseModel, frozen=True):
    provider: str
    source_type: str
    source_record_id: str


class ImportManifest(BaseModel):
    dataset_slug: str
    source_name: str
    source_url: HttpUrl
    source_license: str
    source_observed_at: date | None = None
    retrieved_at: datetime
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    local_filename: str
    request_parameters: dict[str, Any] | None = None


class ImportQualityReport(BaseModel):
    total_records: NonNegativeInt
    promoted_records: NonNegativeInt
    invalid_geometry_count: NonNegativeInt
    missing_name_count: NonNegativeInt
    exact_duplicate_count: NonNegativeInt
    duplicate_candidate_count: NonNegativeInt
    outside_coverage_count: NonNegativeInt = 0
    administrative_join_rate: Annotated[float, Field(ge=0, le=1)] | None = None
    category_counts: dict[str, NonNegativeInt]
    failures: list[str]
