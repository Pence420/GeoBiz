from app.scoring.domain import NormalizationProfileData, ScoreResult, score_location


def _profile(**overrides) -> NormalizationProfileData:
    values = {
        "id": 7,
        "category_slug": "restaurant",
        "radius_m": 1000,
        "dataset_fingerprint": "dataset-v1",
        "version": "v1.0.0",
        "percentiles": {
            "population_density": [10, 20, 30],
            "competition": [1, 3, 8],
            "public_transport": [0, 2, 8],
        },
    }
    values.update(overrides)
    return NormalizationProfileData(**values)


def test_weighted_score_and_inverse_competition() -> None:
    result = score_location(
        category_slug="restaurant",
        radius_m=1000,
        dataset_fingerprint="dataset-v1",
        raw_factors={
            "population_density": 30,
            "competition": 1,
            "public_transport": 8,
        },
        profile=_profile(),
        weights={
            "population_density": 0.4,
            "competition": 0.3,
            "public_transport": 0.3,
        },
    )

    assert isinstance(result, ScoreResult)
    assert result.normalized_factors["population_density"] == 100
    assert result.normalized_factors["competition"] == 100
    assert result.final_score == 100
    assert result.label == "High"


def test_percentile_interpolation_and_winsorization() -> None:
    result = score_location(
        category_slug="restaurant",
        radius_m=1000,
        dataset_fingerprint="dataset-v1",
        raw_factors={
            "population_density": 15,
            "competition": 99,
            "public_transport": -10,
        },
        profile=_profile(),
        weights={
            "population_density": 0.4,
            "competition": 0.3,
            "public_transport": 0.3,
        },
    )

    assert result.normalized_factors == {
        "population_density": 25.0,
        "competition": 0.0,
        "public_transport": 0.0,
    }
    assert result.final_score == 10.0
    assert result.label == "Very Low"


def test_missing_required_factor_is_incomplete_not_zero() -> None:
    result = score_location(
        category_slug="restaurant",
        radius_m=1000,
        dataset_fingerprint="dataset-v1",
        raw_factors={
            "population_density": None,
            "competition": 1,
            "public_transport": 8,
        },
        profile=_profile(),
        weights={
            "population_density": 0.4,
            "competition": 0.3,
            "public_transport": 0.3,
        },
    )

    assert result.status == "incomplete"
    assert result.final_score is None
    assert result.label is None
    assert result.missing_factors == ["population_density"]
    assert result.normalized_factors["population_density"] is None
