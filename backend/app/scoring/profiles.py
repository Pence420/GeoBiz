from app.scoring.domain import NormalizationProfileData

PROFILE_QUANTILES = tuple(index / 100 for index in range(5, 100, 5))


class ProfileMismatchError(ValueError):
    pass


def validate_profile_scope(
    profile: NormalizationProfileData,
    *,
    category_slug: str,
    radius_m: int,
    dataset_fingerprint: str,
) -> None:
    mismatches: list[str] = []
    if profile.category_slug != category_slug:
        mismatches.append("category")
    if profile.radius_m != radius_m:
        mismatches.append("radius")
    if profile.dataset_fingerprint != dataset_fingerprint:
        mismatches.append("dataset fingerprint")
    if mismatches:
        raise ProfileMismatchError(
            "normalization profile does not match " + ", ".join(mismatches)
        )


def percentile_breakpoints(values: list[float]) -> list[float]:
    if not values:
        raise ValueError("cannot build a normalization profile without values")
    ordered = sorted(float(value) for value in values)
    last_index = len(ordered) - 1
    breakpoints: list[float] = []
    for quantile in PROFILE_QUANTILES:
        position = last_index * quantile
        lower_index = int(position)
        upper_index = min(lower_index + 1, last_index)
        fraction = position - lower_index
        value = ordered[lower_index] + (
            ordered[upper_index] - ordered[lower_index]
        ) * fraction
        breakpoints.append(round(value, 6))
    return breakpoints
