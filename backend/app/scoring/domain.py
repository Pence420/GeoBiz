from typing import Literal

from pydantic import BaseModel, Field

ScoreLabel = Literal["Very Low", "Low", "Moderate", "Good", "High"]
NEGATIVE_FACTORS = frozenset({"competition"})


class ScoringConfigurationError(ValueError):
    pass


class NormalizationProfileData(BaseModel):
    id: int
    category_slug: str
    radius_m: int
    dataset_fingerprint: str
    version: str
    percentiles: dict[str, list[float]]


class ScoreResult(BaseModel):
    status: Literal["complete", "incomplete"]
    final_score: float | None = Field(ge=0, le=100)
    label: ScoreLabel | None
    raw_factors: dict[str, float | None]
    normalized_factors: dict[str, float | None]
    weights: dict[str, float]
    missing_factors: list[str]
    scoring_version: str
    profile_id: int


def score_location(
    *,
    category_slug: str,
    radius_m: int,
    dataset_fingerprint: str,
    raw_factors: dict[str, float | None],
    profile: NormalizationProfileData,
    weights: dict[str, float],
) -> ScoreResult:
    from app.scoring.profiles import validate_profile_scope

    validate_profile_scope(
        profile,
        category_slug=category_slug,
        radius_m=radius_m,
        dataset_fingerprint=dataset_fingerprint,
    )
    _validate_weights(weights)

    missing_factors = sorted(
        factor for factor, weight in weights.items()
        if weight > 0 and raw_factors.get(factor) is None
    )
    normalized: dict[str, float | None] = {}
    for factor in weights:
        value = raw_factors.get(factor)
        if value is None:
            normalized[factor] = None
            continue
        breakpoints = profile.percentiles.get(factor)
        if breakpoints is None:
            raise ScoringConfigurationError(
                f"normalization profile is missing factor {factor!r}"
            )
        factor_score = percentile_score(float(value), breakpoints)
        if factor in NEGATIVE_FACTORS:
            factor_score = 100 - factor_score
        normalized[factor] = round(factor_score, 1)

    if missing_factors:
        return ScoreResult(
            status="incomplete",
            final_score=None,
            label=None,
            raw_factors=raw_factors,
            normalized_factors=normalized,
            weights=weights,
            missing_factors=missing_factors,
            scoring_version=profile.version,
            profile_id=profile.id,
        )

    final_score = round(
        sum(float(normalized[factor]) * weight for factor, weight in weights.items()),
        1,
    )
    return ScoreResult(
        status="complete",
        final_score=final_score,
        label=score_label(final_score),
        raw_factors=raw_factors,
        normalized_factors=normalized,
        weights=weights,
        missing_factors=[],
        scoring_version=profile.version,
        profile_id=profile.id,
    )


def percentile_score(value: float, breakpoints: list[float]) -> float:
    if len(breakpoints) < 2:
        raise ScoringConfigurationError("a factor needs at least two percentile breakpoints")
    if any(right < left for left, right in zip(breakpoints, breakpoints[1:])):
        raise ScoringConfigurationError("percentile breakpoints must be non-decreasing")
    if value <= breakpoints[0]:
        return 0.0
    if value >= breakpoints[-1]:
        return 100.0

    interval_rank = 100 / (len(breakpoints) - 1)
    for index, (left, right) in enumerate(zip(breakpoints, breakpoints[1:])):
        if value <= right:
            if right == left:
                return interval_rank * (index + 1)
            fraction = (value - left) / (right - left)
            return interval_rank * (index + fraction)
    return 100.0


def score_label(score: float) -> ScoreLabel:
    if score <= 20:
        return "Very Low"
    if score <= 40:
        return "Low"
    if score <= 60:
        return "Moderate"
    if score <= 80:
        return "Good"
    return "High"


def _validate_weights(weights: dict[str, float]) -> None:
    if not weights:
        raise ScoringConfigurationError("at least one weight is required")
    if any(weight < 0 or weight > 1 for weight in weights.values()):
        raise ScoringConfigurationError("weights must be between zero and one")
    if abs(sum(weights.values()) - 1.0) > 0.0001:
        raise ScoringConfigurationError("weights must sum to 1.0")
