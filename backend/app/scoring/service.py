from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BusinessCategory, NormalizationProfile, ScoringWeight
from app.scoring.domain import NormalizationProfileData, ScoreResult, score_location


class ScoringProfileUnavailableError(LookupError):
    pass


def score_with_stored_profile(
    session: Session,
    *,
    category_slug: str,
    radius_m: int,
    dataset_fingerprint: str,
    raw_factors: dict[str, float | None],
    scoring_version: str = "v1.0.0",
) -> ScoreResult:
    category = session.scalar(
        select(BusinessCategory).where(BusinessCategory.slug == category_slug)
    )
    if category is None:
        raise ScoringProfileUnavailableError("business category is unavailable")
    profile = session.scalar(
        select(NormalizationProfile).where(
            NormalizationProfile.category_id == category.id,
            NormalizationProfile.radius_m == radius_m,
            NormalizationProfile.dataset_fingerprint == dataset_fingerprint,
            NormalizationProfile.version == scoring_version,
        )
    )
    if profile is None:
        raise ScoringProfileUnavailableError(
            "no exact normalization profile exists for this analysis scope"
        )
    rows = session.execute(
        select(ScoringWeight.factor_name, ScoringWeight.weight).where(
            ScoringWeight.category_id == category.id,
            ScoringWeight.version == scoring_version,
            ScoringWeight.is_required.is_(True),
        )
    ).all()
    weights = {name: float(weight) for name, weight in rows if float(weight) > 0}
    return score_location(
        category_slug=category_slug,
        radius_m=radius_m,
        dataset_fingerprint=dataset_fingerprint,
        raw_factors=raw_factors,
        profile=NormalizationProfileData(
            id=profile.id,
            category_slug=category_slug,
            radius_m=profile.radius_m,
            dataset_fingerprint=profile.dataset_fingerprint,
            version=profile.version,
            percentiles=profile.percentiles,
        ),
        weights=weights,
    )
