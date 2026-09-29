from app.scoring.domain import NormalizationProfileData


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
