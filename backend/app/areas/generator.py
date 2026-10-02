from collections.abc import Mapping
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.datasets.service import active_release_id, current_dataset_fingerprint
from app.db.models import (
    BusinessCategory,
    NormalizationProfile,
    OpportunityScore,
    ScoringWeight,
)
from app.scoring.domain import NormalizationProfileData, score_location
from app.scoring.generator import FACTOR_NAMES, SUPPORTED_RADII


def generate_opportunity_scores(
    session: Session,
    *,
    version: str = "v1.0.0",
    release_id: int | None = None,
) -> list[OpportunityScore]:
    """Generate one auditable point-on-surface observation per kelurahan."""
    release_id = release_id or active_release_id(session)
    fingerprint = current_dataset_fingerprint(session)
    categories = session.scalars(
        select(BusinessCategory).where(BusinessCategory.is_active.is_(True))
    ).all()
    generated: list[OpportunityScore] = []

    for category in categories:
        weights = {
            name: float(weight)
            for name, weight in session.execute(
                select(ScoringWeight.factor_name, ScoringWeight.weight).where(
                    ScoringWeight.category_id == category.id,
                    ScoringWeight.version == version,
                    ScoringWeight.is_required.is_(True),
                    ScoringWeight.weight > 0,
                )
            ).all()
        }
        for radius_m in SUPPORTED_RADII:
            profile = session.scalar(
                select(NormalizationProfile).where(
                    NormalizationProfile.data_release_id == release_id,
                    NormalizationProfile.category_id == category.id,
                    NormalizationProfile.radius_m == radius_m,
                    NormalizationProfile.dataset_fingerprint == fingerprint,
                    NormalizationProfile.version == version,
                )
            )
            if profile is None:
                raise ValueError(
                    f"missing normalization profile for {category.slug}/{radius_m}"
                )
            profile_data = NormalizationProfileData(
                id=profile.id,
                category_slug=category.slug,
                radius_m=radius_m,
                dataset_fingerprint=fingerprint,
                version=version,
                percentiles=profile.percentiles,
            )
            for row in _area_metrics(
                session,
                category_slug=category.slug,
                radius_m=radius_m,
                release_id=release_id,
            ):
                raw_factors = {
                    factor: (
                        float(row[factor]) if row[factor] is not None else None
                    )
                    for factor in FACTOR_NAMES
                }
                result = score_location(
                    category_slug=category.slug,
                    radius_m=radius_m,
                    dataset_fingerprint=fingerprint,
                    raw_factors=raw_factors,
                    profile=profile_data,
                    weights=weights,
                )
                if result.status != "complete" or result.final_score is None:
                    raise ValueError(
                        f"incomplete opportunity score for area {row['area_id']}"
                    )
                generated.append(
                    OpportunityScore(
                        data_release_id=release_id,
                        administrative_area_id=row["area_id"],
                        category_id=category.id,
                        radius_m=radius_m,
                        dataset_fingerprint=fingerprint,
                        scoring_version=version,
                        final_score=result.final_score,
                        label=result.label,
                        raw_factors=result.raw_factors,
                        normalized_factors=result.normalized_factors,
                        representative_method="point_on_surface",
                    )
                )

    # Expensive spatial work finishes before this short replacement transaction.
    session.execute(
        delete(OpportunityScore).where(
            OpportunityScore.data_release_id == release_id,
            OpportunityScore.dataset_fingerprint == fingerprint,
            OpportunityScore.scoring_version == version,
        )
    )
    session.add_all(generated)
    session.flush()
    return generated


def _area_metrics(
    session: Session,
    *,
    category_slug: str,
    radius_m: int,
    release_id: int,
) -> list[Mapping[str, Any]]:
    return list(
        session.execute(
            text(
                """
                WITH representative_points AS (
                    SELECT
                        id AS area_id,
                        population_density,
                        ST_PointOnSurface(geom) AS geom
                    FROM administrative_areas
                    WHERE data_release_id = :release_id
                      AND area_type = 'kelurahan'
                      AND population_density IS NOT NULL
                )
                SELECT
                    point.area_id,
                    point.population_density::float AS population_density,
                    (
                        SELECT count(*)::float
                        FROM businesses AS business
                        JOIN business_categories AS category
                          ON category.id = business.category_id
                        WHERE category.slug = :category_slug
                          AND business.data_release_id = :release_id
                          AND business.geom && ST_Expand(point.geom, :radius_degrees)
                          AND ST_DWithin(
                              business.geom::geography,
                              point.geom::geography,
                              :radius_m
                          )
                    ) AS competition,
                    (
                        SELECT count(DISTINCT coalesce(stop.parent_stop_id, stop.id))::float
                        FROM transport_stops AS stop
                        WHERE stop.data_release_id = :release_id
                          AND stop.geom && ST_Expand(point.geom, :radius_degrees)
                          AND ST_DWithin(
                              stop.geom::geography,
                              point.geom::geography,
                              :radius_m
                          )
                    ) AS public_transport,
                    (
                        SELECT count(*)::float
                        FROM pois AS poi
                        WHERE poi.data_release_id = :release_id
                          AND poi.poi_type = 'commercial'
                          AND poi.geom && ST_Expand(point.geom, :radius_degrees)
                          AND ST_DWithin(
                              poi.geom::geography,
                              point.geom::geography,
                              :radius_m
                          )
                    ) AS commercial_activity,
                    (
                        SELECT count(*)::float
                        FROM pois AS poi
                        WHERE poi.data_release_id = :release_id
                          AND poi.poi_type = 'office'
                          AND poi.geom && ST_Expand(point.geom, :radius_degrees)
                          AND ST_DWithin(
                              poi.geom::geography,
                              point.geom::geography,
                              :radius_m
                          )
                    ) AS office_activity,
                    greatest(0.0, 5000.0 - road.distance_m) AS road_accessibility,
                    (
                        SELECT count(*)::float
                        FROM pois AS poi
                        WHERE poi.data_release_id = :release_id
                          AND poi.poi_type IN ('hospital', 'clinic', 'doctors')
                          AND poi.geom && ST_Expand(point.geom, :radius_degrees)
                          AND ST_DWithin(
                              poi.geom::geography,
                              point.geom::geography,
                              :radius_m
                          )
                    ) AS healthcare_proximity
                FROM representative_points AS point
                JOIN LATERAL (
                    SELECT ST_Distance(
                        road.geom::geography,
                        point.geom::geography
                    ) AS distance_m
                    FROM roads AS road
                    WHERE road.data_release_id = :release_id
                    ORDER BY road.geom <-> point.geom
                    LIMIT 1
                ) AS road ON true
                ORDER BY point.area_id
                """
            ),
            {
                "category_slug": category_slug,
                "radius_m": radius_m,
                "radius_degrees": radius_m / 110_000,
                "release_id": release_id,
            },
        ).mappings()
    )
