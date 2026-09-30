import pytest

from app.scoring.domain import NormalizationProfileData
from app.scoring.profiles import (
    ProfileMismatchError,
    percentile_breakpoints,
    validate_profile_scope,
)


def test_profile_must_match_category_radius_and_dataset() -> None:
    profile = NormalizationProfileData(
        id=1,
        category_slug="restaurant",
        radius_m=1000,
        dataset_fingerprint="dataset-v1",
        version="v1.0.0",
        percentiles={"competition": [1, 2]},
    )

    with pytest.raises(ProfileMismatchError, match="radius"):
        validate_profile_scope(
            profile,
            category_slug="restaurant",
            radius_m=500,
            dataset_fingerprint="dataset-v1",
        )


def test_profile_rejects_wrong_dataset_fingerprint() -> None:
    profile = NormalizationProfileData(
        id=1,
        category_slug="gym",
        radius_m=1000,
        dataset_fingerprint="old-data",
        version="v1.0.0",
        percentiles={"competition": [1, 2]},
    )

    with pytest.raises(ProfileMismatchError, match="dataset"):
        validate_profile_scope(
            profile,
            category_slug="gym",
            radius_m=1000,
            dataset_fingerprint="new-data",
        )


def test_percentile_breakpoints_winsorize_at_fifth_and_ninety_fifth() -> None:
    values = list(range(101))

    breakpoints = percentile_breakpoints(values)

    assert breakpoints[0] == 5.0
    assert breakpoints[-1] == 95.0
    assert len(breakpoints) == 19
