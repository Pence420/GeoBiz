from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from app.analytics.contracts import (
    AnalyticsResponse,
    CategoryCount,
    CategoryMethodology,
    CoverageMetric,
    MethodologyDataset,
    MethodologyResponse,
    OpportunitySummary,
    PopulationCompetitionPoint,
    ScoreBand,
    SearchResult,
)
from app.datasets.service import (
    active_release_id,
    current_dataset_fingerprint,
    list_dataset_snapshots,
)
from app.db.models import Business, BusinessCategory, ScoringWeight

SCORING_VERSION = "v1.0.0"
SUPPORTED_RADII = [500, 1000, 2000, 3000, 5000]
FACTOR_DEFINITIONS = {
    "population_density": "Official residents per square kilometre in the containing kelurahan.",
    "competition": "Same-category OpenStreetMap businesses inside the selected radius; normalized inversely.",
    "public_transport": "Distinct official TransJakarta stations and stops inside the selected radius.",
    "commercial_activity": "Mapped malls, markets, and commercial places inside the selected radius.",
    "office_activity": "Mapped office places inside the selected radius.",
    "road_accessibility": "Proximity to the nearest mapped major road, capped at five kilometres.",
    "healthcare_proximity": "Mapped hospitals, clinics, and doctors inside the selected radius.",
}


def analytics(
    session: Session,
    *,
    category_slug: str,
    radius_m: int,
) -> AnalyticsResponse:
    fingerprint = current_dataset_fingerprint(session)
    release_id = active_release_id(session)
    category_counts = [
        CategoryCount(category=row.slug, count=row.business_count)
        for row in session.execute(
            select(
                BusinessCategory.slug,
                func.count(Business.id).label("business_count"),
            )
            .outerjoin(
                Business,
                and_(
                    Business.category_id == BusinessCategory.id,
                    Business.data_release_id == release_id,
                ),
            )
            .where(BusinessCategory.is_active.is_(True))
            .group_by(BusinessCategory.id)
            .order_by(BusinessCategory.id)
        ).mappings()
    ]
    parameters = {
        "category_slug": category_slug,
        "radius_m": radius_m,
        "fingerprint": fingerprint,
        "scoring_version": SCORING_VERSION,
        "release_id": release_id,
    }
    rows = session.execute(
        text(
            """
            SELECT
                score.administrative_area_id AS area_id,
                area.name AS area_name,
                score.final_score::float AS final_score,
                score.label,
                (score.raw_factors ->> 'population_density')::float
                    AS population_density,
                (score.raw_factors ->> 'competition')::float
                    AS competitor_count
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
            """
        ),
        parameters,
    ).mappings().all()
    if not rows:
        raise LookupError("opportunity scores are unavailable for this analytics scope")

    band_specs = [
        ("Very Low", 0, 20),
        ("Low", 21, 40),
        ("Moderate", 41, 60),
        ("Good", 61, 80),
        ("High", 81, 100),
    ]
    distribution = [
        ScoreBand(
            label=label,
            minimum=minimum,
            maximum=maximum,
            area_count=sum(1 for row in rows if row["label"] == label),
        )
        for label, minimum, maximum in band_specs
    ]
    coverage_row = session.execute(
        text(
            """
            SELECT
                (SELECT count(*) FROM administrative_areas
                    WHERE data_release_id = :release_id
                      AND area_type = 'kelurahan' AND population_density IS NOT NULL)
                    AS populated_areas,
                (SELECT count(*) FROM transport_stops
                    WHERE data_release_id = :release_id) AS transport_stops,
                (SELECT count(*) FROM pois
                    WHERE data_release_id = :release_id) AS pois,
                (SELECT count(*) FROM roads
                    WHERE data_release_id = :release_id) AS roads,
                (SELECT 100.0 * count(name) / nullif(count(*), 0) FROM businesses
                    WHERE data_release_id = :release_id)
                    AS named_business_percent
            """
        ),
        {"release_id": release_id},
    ).mappings().one()
    coverage = [
        CoverageMetric(
            key="populated_areas",
            label="Population-matched kelurahan",
            value=float(coverage_row["populated_areas"]),
            unit="areas",
            definition="Kelurahan polygons with an official population-density value.",
        ),
        CoverageMetric(
            key="transport_stops",
            label="Official transit records",
            value=float(coverage_row["transport_stops"]),
            unit="records",
            definition="Stops and stations from the promoted TransJakarta GTFS snapshot.",
        ),
        CoverageMetric(
            key="supporting_pois",
            label="Supporting POIs",
            value=float(coverage_row["pois"]),
            unit="records",
            definition="Traceable commercial, office, education, and healthcare OpenStreetMap records.",
        ),
        CoverageMetric(
            key="major_roads",
            label="Mapped road segments",
            value=float(coverage_row["roads"]),
            unit="segments",
            definition="OpenStreetMap road geometries used for accessibility analysis.",
        ),
        CoverageMetric(
            key="named_business_percent",
            label="Named business coverage",
            value=round(float(coverage_row["named_business_percent"] or 0), 1),
            unit="percent",
            definition="Share of promoted business records that contain a source-provided name.",
        ),
    ]
    return AnalyticsResponse(
        business_category=category_slug,
        radius_m=radius_m,
        scoring_version=SCORING_VERSION,
        dataset_fingerprint=fingerprint,
        category_counts=category_counts,
        top_opportunities=[OpportunitySummary(**row) for row in rows[:10]],
        score_distribution=distribution,
        population_competition=[PopulationCompetitionPoint(**row) for row in rows],
        coverage=coverage,
    )


def methodology(session: Session) -> MethodologyResponse:
    fingerprint = current_dataset_fingerprint(session)
    weight_rows = session.execute(
        select(
            BusinessCategory.slug,
            ScoringWeight.factor_name,
            ScoringWeight.weight,
        )
        .join(ScoringWeight, ScoringWeight.category_id == BusinessCategory.id)
        .where(ScoringWeight.version == SCORING_VERSION)
        .order_by(BusinessCategory.id, ScoringWeight.id)
    ).all()
    weights_by_category: dict[str, dict[str, float]] = {}
    for category, factor, weight in weight_rows:
        weights_by_category.setdefault(category, {})[factor] = float(weight)
    datasets = list_dataset_snapshots(session)
    return MethodologyResponse(
        coverage="DKI Jakarta",
        scoring_version=SCORING_VERSION,
        dataset_fingerprint=fingerprint,
        supported_radii_m=SUPPORTED_RADII,
        representative_area_method="ST_PointOnSurface: one guaranteed in-polygon observation per kelurahan.",
        normalization=(
            "Every raw factor is mapped to 0–100 against versioned DKI-wide percentile "
            "breakpoints for the same category, radius, and dataset fingerprint. "
            "Competition is inverted after normalization."
        ),
        factor_definitions=FACTOR_DEFINITIONS,
        categories=[
            CategoryMethodology(category=category, weights=weights)
            for category, weights in weights_by_category.items()
        ],
        datasets=[
            MethodologyDataset(**snapshot.model_dump(exclude={"sha256"}))
            for snapshot in datasets
        ],
        limitations=[
            "OpenStreetMap coverage reflects community-contributed records and can be incomplete.",
            "Population density is an official annual kelurahan aggregate, not real-time footfall.",
            "Area scores use one representative point and do not imply uniform suitability across a polygon.",
            "GeoBiz supports initial site screening; it does not predict or guarantee business success.",
        ],
    )


def search(session: Session, *, query: str, limit: int) -> list[SearchResult]:
    release_id = active_release_id(session)
    coordinate = _parse_coordinate(query)
    results: list[SearchResult] = []
    if coordinate is not None:
        latitude, longitude = coordinate
        inside = session.scalar(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM administrative_areas
                    WHERE data_release_id = :release_id
                      AND official_code = 'ID-JK'
                      AND ST_Covers(geom, ST_SetSRID(ST_Point(:longitude, :latitude), 4326))
                )
                """
            ),
            {
                "longitude": longitude,
                "latitude": latitude,
                "release_id": release_id,
            },
        )
        if inside:
            results.append(
                SearchResult(
                    id=f"coordinate:{latitude:.6f},{longitude:.6f}",
                    name=f"{latitude:.6f}, {longitude:.6f}",
                    result_type="coordinate",
                    subtitle="Coordinate inside DKI Jakarta",
                    latitude=latitude,
                    longitude=longitude,
                )
            )
    if len(query.strip()) < 2:
        return results
    rows = session.execute(
        text(
            """
            WITH candidates AS (
                SELECT
                    'area:' || area.id AS id,
                    area.name,
                    'area' AS result_type,
                    initcap(area.area_type) AS subtitle,
                    ST_X(ST_PointOnSurface(area.geom)) AS longitude,
                    ST_Y(ST_PointOnSurface(area.geom)) AS latitude,
                    NULL::text AS source_record_id,
                    1 AS priority
                FROM administrative_areas AS area
                WHERE area.data_release_id = :release_id
                  AND area.name ILIKE :pattern
                  AND area.area_type IN ('kelurahan', 'kecamatan', 'city')
                UNION ALL
                SELECT
                    'business:' || business.id,
                    business.name,
                    'business',
                    initcap(category.name),
                    ST_X(business.geom),
                    ST_Y(business.geom),
                    business.source_record_id,
                    2
                FROM businesses AS business
                JOIN business_categories AS category ON category.id = business.category_id
                WHERE business.data_release_id = :release_id
                  AND business.name IS NOT NULL AND business.name ILIKE :pattern
                UNION ALL
                SELECT
                    'landmark:' || poi.id,
                    poi.name,
                    'landmark',
                    initcap(replace(poi.poi_type, '_', ' ')),
                    ST_X(ST_PointOnSurface(poi.geom)),
                    ST_Y(ST_PointOnSurface(poi.geom)),
                    poi.source_record_id,
                    3
                FROM pois AS poi
                WHERE poi.data_release_id = :release_id
                  AND poi.name IS NOT NULL AND poi.name ILIKE :pattern
            )
            SELECT id, name, result_type, subtitle, longitude, latitude,
                   source_record_id
            FROM candidates
            ORDER BY
                CASE WHEN lower(name) = lower(:query) THEN 0 ELSE priority END,
                length(name), name
            LIMIT :limit
            """
        ),
        {
            "query": query.strip(),
            "pattern": f"%{query.strip()}%",
            "limit": limit,
            "release_id": release_id,
        },
    ).mappings()
    results.extend(SearchResult(**row) for row in rows)
    return results[:limit]


def _parse_coordinate(query: str) -> tuple[float, float] | None:
    parts = [part.strip() for part in query.split(",")]
    if len(parts) != 2:
        return None
    try:
        latitude, longitude = (float(part) for part in parts)
    except ValueError:
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return latitude, longitude
