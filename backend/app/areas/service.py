import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.contracts import GeoJsonFeature, GeoJsonFeatureCollection
from app.areas.contracts import AreaRankingItem, AreaRankingResponse
from app.datasets.service import active_release_id, current_dataset_fingerprint


class OpportunityScoresUnavailableError(LookupError):
    pass


def opportunity_map(
    session: Session,
    *,
    category_slug: str,
    radius_m: int,
    west: float,
    south: float,
    east: float,
    north: float,
    scoring_version: str = "v1.0.0",
) -> GeoJsonFeatureCollection:
    fingerprint = current_dataset_fingerprint(session)
    release_id = active_release_id(session)
    rows = session.execute(
        text(
            """
            WITH ranked AS (
                SELECT
                    score.id,
                    score.administrative_area_id,
                    area.name,
                    area.geom,
                    score.final_score,
                    score.label,
                    score.normalized_factors,
                    score.raw_factors,
                    score.representative_method,
                    row_number() OVER (
                        ORDER BY score.final_score DESC, area.name, area.id
                    ) AS rank
                FROM opportunity_scores AS score
                JOIN business_categories AS category
                  ON category.id = score.category_id
                JOIN administrative_areas AS area
                  ON area.id = score.administrative_area_id
                WHERE category.slug = :category_slug
                  AND score.data_release_id = :release_id
                  AND area.data_release_id = :release_id
                  AND score.radius_m = :radius_m
                  AND score.dataset_fingerprint = :fingerprint
                  AND score.scoring_version = :scoring_version
            )
            SELECT
                ranked.id,
                ranked.administrative_area_id,
                ranked.name,
                ranked.final_score::float AS final_score,
                ranked.label,
                ranked.normalized_factors,
                ranked.raw_factors,
                ranked.representative_method,
                ST_X(ST_PointOnSurface(ranked.geom)) AS longitude,
                ST_Y(ST_PointOnSurface(ranked.geom)) AS latitude,
                ranked.rank,
                ST_AsGeoJSON(
                    ST_Multi(ST_SimplifyPreserveTopology(ranked.geom, 0.00003))
                )::json AS geometry
            FROM ranked
            WHERE ranked.geom && ST_MakeEnvelope(
                :west, :south, :east, :north, 4326
            )
            ORDER BY ranked.rank
            """
        ),
        {
            "category_slug": category_slug,
            "release_id": release_id,
            "radius_m": radius_m,
            "fingerprint": fingerprint,
            "scoring_version": scoring_version,
            "west": west,
            "south": south,
            "east": east,
            "north": north,
        },
    ).mappings().all()
    if not rows:
        raise OpportunityScoresUnavailableError(
            "opportunity scores have not been generated for this dataset scope"
        )
    return GeoJsonFeatureCollection(
        attribution="Satu Data Jakarta; © OpenStreetMap contributors",
        features=[
            GeoJsonFeature(
                id=row["id"],
                geometry=_json_value(row["geometry"]),
                properties={
                    "area_id": row["administrative_area_id"],
                    "name": row["name"],
                    "rank": row["rank"],
                    "final_score": row["final_score"],
                    "label": row["label"],
                    "normalized_factors": row["normalized_factors"],
                    "raw_factors": row["raw_factors"],
                    "representative_method": row["representative_method"],
                    "longitude": row["longitude"],
                    "latitude": row["latitude"],
                    "scoring_version": scoring_version,
                    "dataset_fingerprint": fingerprint,
                },
            )
            for row in rows
        ],
    )


def area_rankings(
    session: Session,
    *,
    category_slug: str,
    radius_m: int,
    limit: int,
    scoring_version: str = "v1.0.0",
) -> AreaRankingResponse:
    fingerprint = current_dataset_fingerprint(session)
    release_id = active_release_id(session)
    rows = session.execute(
        text(
            """
            SELECT
                score.administrative_area_id AS area_id,
                area.name AS area_name,
                row_number() OVER (
                    ORDER BY score.final_score DESC, area.name
                ) AS rank,
                score.final_score::float AS final_score,
                score.label,
                ST_X(ST_PointOnSurface(area.geom)) AS longitude,
                ST_Y(ST_PointOnSurface(area.geom)) AS latitude,
                score.normalized_factors,
                score.raw_factors,
                score.representative_method
            FROM opportunity_scores AS score
            JOIN business_categories AS category ON category.id = score.category_id
            JOIN administrative_areas AS area
              ON area.id = score.administrative_area_id
            WHERE category.slug = :category_slug
              AND score.data_release_id = :release_id
              AND area.data_release_id = :release_id
              AND score.radius_m = :radius_m
              AND score.dataset_fingerprint = :fingerprint
              AND score.scoring_version = :scoring_version
            ORDER BY score.final_score DESC, area.name
            LIMIT :limit
            """
        ),
        {
            "category_slug": category_slug,
            "release_id": release_id,
            "radius_m": radius_m,
            "fingerprint": fingerprint,
            "scoring_version": scoring_version,
            "limit": limit,
        },
    ).mappings().all()
    if not rows:
        raise OpportunityScoresUnavailableError(
            "opportunity scores have not been generated for this dataset scope"
        )
    return AreaRankingResponse(
        business_category=category_slug,
        radius_m=radius_m,
        scoring_version=scoring_version,
        dataset_fingerprint=fingerprint,
        items=[AreaRankingItem(**row) for row in rows],
    )


def _json_value(value: Any) -> dict[str, Any]:
    return json.loads(value) if isinstance(value, str) else value
