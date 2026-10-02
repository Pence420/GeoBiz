import pytest

from app.analysis.contracts import (
    AnalysisCoverage,
    AnalyzeLocationRequest,
    ContainingArea,
    LocationEvidence,
    NearbyMetrics,
    PoiBreakdown,
)
from app.analysis.service import AnalysisService, LocationOutsideCoverageError
from app.scoring.domain import ScoreResult


class FakeRepository:
    def __init__(self, area: ContainingArea | None) -> None:
        self.area = area

    def find_containing_area(self, **_coordinates):
        return self.area

    def calculate_metrics(self, **_arguments):
        return NearbyMetrics(
            competitor_count=4,
            transport_stop_count=None,
            commercial_poi_count=None,
            office_count=None,
            university_count=None,
            healthcare_count=None,
            population_density=None,
            nearest_major_road_m=None,
        )

    def detailed_evidence(self, **_arguments):
        return LocationEvidence(
            competitor_subtype_counts={},
            nearest_competitors=[],
            nearest_transport=None,
            nearest_major_road=None,
            poi_breakdown=PoiBreakdown(
                commercial={}, office={}, education={}, healthcare={}
            ),
            coverage=AnalysisCoverage(
                total_businesses=0,
                named_business_percent=0,
                missing_source_fields={},
            ),
        )


def test_point_outside_dki_is_rejected() -> None:
    service = AnalysisService(
        repository=FakeRepository(None),
        score_provider=lambda **_kwargs: None,
        fingerprint_provider=lambda: "dataset-v1",
        release_version_provider=lambda: ("v2.0.0", "v2.0.0"),
        snapshots_provider=lambda: [],
    )

    with pytest.raises(LocationOutsideCoverageError) as error:
        service.analyze(
            AnalyzeLocationRequest(
                longitude=110, latitude=-7, business_category="fnb"
            )
        )

    assert error.value.code == "LOCATION_OUTSIDE_COVERAGE"


def test_missing_source_metrics_are_forwarded_as_none_not_zero() -> None:
    captured = {}

    def score_provider(**kwargs):
        captured.update(kwargs)
        return ScoreResult(
            status="incomplete",
            final_score=None,
            label=None,
            raw_factors=kwargs["raw_factors"],
            normalized_factors={key: None for key in kwargs["raw_factors"]},
            weights={"population_density": 1.0},
            missing_factors=["population_density"],
            scoring_version="v2.0.0",
            profile_id=1,
        )

    service = AnalysisService(
        repository=FakeRepository(
            ContainingArea(
                id=1,
                name="DKI Jakarta",
                official_code="ID-JK",
                population_density=None,
            )
        ),
        score_provider=score_provider,
        fingerprint_provider=lambda: "dataset-v1",
        release_version_provider=lambda: ("v2.0.0", "v2.0.0"),
        snapshots_provider=lambda: [],
    )

    response = service.analyze(
        AnalyzeLocationRequest(
            longitude=106.8, latitude=-6.2, business_category="fnb"
        )
    )

    assert captured["raw_factors"]["competition"] == 4
    assert captured["raw_factors"]["population_density"] is None
    assert captured["raw_factors"]["public_transport"] is None
    assert response.score.status == "incomplete"


def test_granular_area_uses_parent_dki_coverage_code() -> None:
    service = AnalysisService(
        repository=FakeRepository(
            ContainingArea(
                id=246,
                name="GAMBIR",
                official_code=None,
                coverage_official_code="ID-JK",
                population_density=1093.87,
            )
        ),
        score_provider=lambda **kwargs: ScoreResult(
            status="complete",
            final_score=50.0,
                label="Moderate",
            raw_factors=kwargs["raw_factors"],
            normalized_factors={key: 50.0 for key in kwargs["raw_factors"]},
            weights={"competition": 1.0},
            missing_factors=[],
            scoring_version="v2.0.0",
            profile_id=1,
        ),
        fingerprint_provider=lambda: "dataset-v1",
        release_version_provider=lambda: ("v2.0.0", "v2.0.0"),
        snapshots_provider=lambda: [],
    )

    response = service.analyze(
        AnalyzeLocationRequest(
            longitude=106.8272,
            latitude=-6.1754,
            business_category="fnb",
        )
    )

    assert response.containing_area.name == "GAMBIR"
    assert response.containing_area.coverage_official_code == "ID-JK"
