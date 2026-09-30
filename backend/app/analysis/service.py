from collections.abc import Callable
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.analysis.contracts import (
    AnalyzeLocationRequest,
    AnalyzeLocationResponse,
    ContainingArea,
    NearbyMetrics,
)
from app.scoring.domain import ScoreResult


class LocationOutsideCoverageError(ValueError):
    code = "LOCATION_OUTSIDE_COVERAGE"

    def __init__(self) -> None:
        super().__init__("selected location is outside DKI Jakarta coverage")


class AnalysisRepository(Protocol):
    def find_containing_area(
        self, *, longitude: float, latitude: float
    ) -> ContainingArea | None: ...

    def calculate_metrics(
        self,
        *,
        longitude: float,
        latitude: float,
        category_slug: str,
        radius_m: int,
    ) -> NearbyMetrics: ...


class AnalysisService:
    def __init__(
        self,
        *,
        repository: AnalysisRepository,
        score_provider: Callable[..., ScoreResult],
        fingerprint_provider: Callable[[], str],
    ) -> None:
        self.repository = repository
        self.score_provider = score_provider
        self.fingerprint_provider = fingerprint_provider

    def analyze(self, request: AnalyzeLocationRequest) -> AnalyzeLocationResponse:
        area = self.repository.find_containing_area(
            longitude=request.longitude, latitude=request.latitude
        )
        if area is None or (
            area.coverage_official_code or area.official_code
        ) != "ID-JK":
            raise LocationOutsideCoverageError()

        metrics = self.repository.calculate_metrics(
            longitude=request.longitude,
            latitude=request.latitude,
            category_slug=request.business_category,
            radius_m=request.radius_m,
        )
        dataset_fingerprint = self.fingerprint_provider()
        raw_factors: dict[str, float | None] = {
            "population_density": metrics.population_density,
            "competition": float(metrics.competitor_count),
            "public_transport": _as_float(metrics.transport_stop_count),
            "commercial_activity": _as_float(metrics.commercial_poi_count),
            "office_activity": _as_float(metrics.office_count),
            "road_accessibility": (
                None
                if metrics.nearest_major_road_m is None
                else max(0.0, 5000.0 - metrics.nearest_major_road_m)
            ),
            "healthcare_proximity": _as_float(metrics.healthcare_count),
        }
        score = self.score_provider(
            category_slug=request.business_category,
            radius_m=request.radius_m,
            dataset_fingerprint=dataset_fingerprint,
            raw_factors=raw_factors,
        )
        missing_sources = [
            factor for factor, value in raw_factors.items() if value is None
        ]
        limitations = [
            "OpenStreetMap coverage depends on community-contributed records.",
            "The score is comparative location evidence, not a success guarantee.",
        ]
        if missing_sources:
            limitations.append(
                "Unavailable factors were not replaced with zero: "
                + ", ".join(missing_sources)
                + "."
            )
        return AnalyzeLocationResponse(
            latitude=request.latitude,
            longitude=request.longitude,
            business_category=request.business_category,
            radius_m=request.radius_m,
            containing_area=area,
            nearby_metrics=metrics,
            score=score,
            dataset_fingerprint=dataset_fingerprint,
            limitations=limitations,
        )


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def build_analysis_service(session: Session) -> AnalysisService:
    from app.analysis.repository import SpatialRepository
    from app.datasets.service import current_dataset_fingerprint
    from app.scoring.service import score_with_stored_profile

    return AnalysisService(
        repository=SpatialRepository(session),
        score_provider=lambda **arguments: score_with_stored_profile(
            session, **arguments
        ),
        fingerprint_provider=lambda: current_dataset_fingerprint(session),
    )
