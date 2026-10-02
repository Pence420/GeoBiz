from collections.abc import Mapping
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.db.models import BusinessCategory, DataRelease, NormalizationProfile
from app.datasets.service import active_release_id, current_dataset_fingerprint
from app.releases.service import LEGACY_CATEGORY_SLUGS, V2_CATEGORY_SLUGS
from app.scoring.profiles import percentile_breakpoints

SUPPORTED_RADII = (500, 1000, 2000, 3000, 5000)
FACTOR_NAMES = (
    "population_density",
    "competition",
    "public_transport",
    "commercial_activity",
    "office_activity",
    "road_accessibility",
    "healthcare_proximity",
)


def generate_normalization_profiles(
    session: Session,
    *,
    version: str = "v1.0.0",
    grid_size_m: int = 1000,
    release_id: int | None = None,
) -> list[NormalizationProfile]:
    release_id = release_id or active_release_id(session)
    release = session.get(DataRelease, release_id)
    if release is None:
        raise ValueError(f"data release {release_id} does not exist")
    fingerprint = (
        current_dataset_fingerprint(session)
        if release.status == "active"
        else release.dataset_fingerprint
    )
    category_slugs = (
        V2_CATEGORY_SLUGS
        if release.taxonomy_version == "v2.0.0"
        else LEGACY_CATEGORY_SLUGS
    )
    categories = session.scalars(
        select(BusinessCategory).where(BusinessCategory.slug.in_(category_slugs))
    ).all()
    session.execute(
        delete(NormalizationProfile).where(
            NormalizationProfile.data_release_id == release_id,
            NormalizationProfile.dataset_fingerprint == fingerprint,
            NormalizationProfile.version == version,
        )
    )
    profiles: list[NormalizationProfile] = []
    for category in categories:
        for radius_m in SUPPORTED_RADII:
            rows = _reference_metrics(
                session,
                category_slug=category.slug,
                radius_m=radius_m,
                grid_size_m=grid_size_m,
                release_id=release_id,
            )
            if not rows:
                raise ValueError("hex reference grid produced no DKI observations")
            percentiles = {
                factor: percentile_breakpoints(
                    [float(row[factor]) for row in rows if row[factor] is not None]
                )
                for factor in FACTOR_NAMES
            }
            profile = NormalizationProfile(
                data_release_id=release_id,
                category_id=category.id,
                radius_m=radius_m,
                dataset_fingerprint=fingerprint,
                version=version,
                percentiles=percentiles,
                sample_count=len(rows),
            )
            session.add(profile)
            profiles.append(profile)
    session.flush()
    return profiles


def _reference_metrics(
    session: Session,
    *,
    category_slug: str,
    radius_m: int,
    grid_size_m: int,
    release_id: int,
) -> list[Mapping[str, Any]]:
    return list(
        session.execute(
            text(
                """
                WITH kelurahan_union AS (
                    SELECT ST_UnaryUnion(ST_Collect(geom)) AS geom
                    FROM administrative_areas
                    WHERE data_release_id = :release_id
                      AND area_type = 'kelurahan'
                      AND population_density IS NOT NULL
                ),
                land_utm AS (
                    SELECT ST_Transform(geom, 32748) AS geom
                    FROM kelurahan_union
                ),
                grid AS (
                    SELECT (ST_HexagonGrid(:grid_size_m, geom)).geom AS geom
                    FROM land_utm
                ),
                reference_points AS (
                    SELECT ST_Transform(ST_Centroid(grid.geom), 4326) AS geom
                    FROM grid, land_utm
                    WHERE ST_Covers(land_utm.geom, ST_Centroid(grid.geom))
                )
                SELECT
                    area.population_density::float AS population_density,
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
                FROM reference_points AS point
                JOIN LATERAL (
                    SELECT population_density
                    FROM administrative_areas
                    WHERE data_release_id = :release_id
                      AND area_type = 'kelurahan'
                      AND ST_Covers(geom, point.geom)
                    ORDER BY ST_Area(geom)
                    LIMIT 1
                ) AS area ON true
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
                """
            ),
            {
                "category_slug": category_slug,
                "radius_m": radius_m,
                # Coarse equatorial bbox prefilter only; geography remains authoritative.
                "radius_degrees": radius_m / 110_000,
                "grid_size_m": grid_size_m,
                "release_id": release_id,
            },
        ).mappings()
    )
