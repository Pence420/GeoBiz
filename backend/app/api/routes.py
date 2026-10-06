import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from app.analysis.contracts import AnalyzeLocationRequest, AnalyzeLocationResponse
from app.analysis.service import LocationOutsideCoverageError, build_analysis_service
from app.analytics.contracts import AnalyticsResponse, MethodologyResponse, SearchResult
from app.analytics.service import analytics, methodology, search
from app.areas.contracts import AreaRankingResponse
from app.areas.service import (
    OpportunityScoresUnavailableError,
    area_rankings,
    opportunity_map,
)
from app.api.contracts import (
    ApiError,
    CategorySummary,
    DatasetSummary,
    GeoJsonFeature,
    GeoJsonFeatureCollection,
    MetadataResponse,
)
from app.datasets.service import active_release_id, current_dataset_fingerprint
from app.demographics.contracts import DemographicsResponse
from app.demographics.service import demographics
from app.db.models import (
    Business,
    BusinessCategory,
    DataReleaseSource,
    DataRelease,
    DatasetSource,
)
from app.db.session import get_session
from app.scoring.service import ScoringProfileUnavailableError
from app.releases.contracts import MapConfig, RefreshStatusResponse, ReleaseSummary
from app.datasets.service import active_release
from app.taxonomy.businesses import BusinessCategorySlug

router = APIRouter(prefix="/api")

SUPPORTED_RADII = (500, 1000, 2000, 3000, 5000)


@router.get("/demographics", response_model=DemographicsResponse)
def population_demographics(session: Annotated[Session, Depends(get_session)]):
    try:
        return demographics(session)
    except LookupError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "DEMOGRAPHICS_UNAVAILABLE", "message": str(error)},
        ) from error


def _validate_bbox(*, west: float, south: float, east: float, north: float) -> None:
    if west >= east or south >= north:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_BBOX", "message": "bbox bounds are inverted"},
        )


@router.get("/business-categories", response_model=list[CategorySummary])
@router.get("/categories", response_model=list[CategorySummary], include_in_schema=False)
def list_categories(session: Annotated[Session, Depends(get_session)]):
    if active_release(session).taxonomy_version != "v2.0.0":
        raise HTTPException(
            status_code=409,
            detail={"code": "V2_RELEASE_REQUIRED", "message": "GeoBiz v2 data is not active"},
        )
    release_id = active_release_id(session)
    rows = session.execute(
        select(
            BusinessCategory.slug,
            BusinessCategory.name,
            BusinessCategory.description,
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
    return [CategorySummary(**row) for row in rows]


@router.get("/businesses", response_model=GeoJsonFeatureCollection)
def list_businesses(
    session: Annotated[Session, Depends(get_session)],
    category: BusinessCategorySlug | None = None,
    west: Annotated[float, Query(ge=-180, le=180)] = 106.45,
    south: Annotated[float, Query(ge=-90, le=90)] = -6.38,
    east: Annotated[float, Query(ge=-180, le=180)] = 106.98,
    north: Annotated[float, Query(ge=-90, le=90)] = -5.60,
    limit: Annotated[int, Query(ge=1, le=5000)] = 3000,
):
    _validate_bbox(west=west, south=south, east=east, north=north)
    release_id = active_release_id(session)
    rows = session.execute(
        text(
            """
            SELECT
                business.id,
                business.name,
                category.slug AS category,
                business.source_type,
                business.source_record_id,
                business.business_subtype,
                business.taxonomy_version,
                business.original_tags ->> 'brand' AS brand,
                business.original_tags ->> 'operator' AS operator,
                business.original_tags ->> 'opening_hours' AS opening_hours,
                coalesce(
                    business.original_tags ->> 'contact:phone',
                    business.original_tags ->> 'phone'
                ) AS phone,
                coalesce(
                    business.original_tags ->> 'contact:website',
                    business.original_tags ->> 'website'
                ) AS website,
                nullif(concat_ws(', ',
                    business.original_tags ->> 'addr:housenumber',
                    business.original_tags ->> 'addr:street',
                    business.original_tags ->> 'addr:suburb',
                    business.original_tags ->> 'addr:city'
                ), '') AS address,
                ST_AsGeoJSON(business.geom)::json AS geometry
            FROM businesses AS business
            JOIN business_categories AS category ON category.id = business.category_id
            WHERE (
                CAST(:category AS text) IS NULL
                OR category.slug = CAST(:category AS text)
            )
              AND business.data_release_id = :release_id
              AND business.geom && ST_MakeEnvelope(
                  :west, :south, :east, :north, 4326
              )
            ORDER BY business.id
            LIMIT :limit
            """
        ),
        {
            "category": category,
            "release_id": release_id,
            "west": west,
            "south": south,
            "east": east,
            "north": north,
            "limit": limit,
        },
    ).mappings()
    features = [
        GeoJsonFeature(
            id=row["id"],
            geometry=(
                json.loads(row["geometry"])
                if isinstance(row["geometry"], str)
                else row["geometry"]
            ),
            properties={
                "name": row["name"],
                "category": row["category"],
                "source_type": row["source_type"],
                "source_record_id": row["source_record_id"],
                "business_subtype": row["business_subtype"],
                "taxonomy_version": row["taxonomy_version"],
                "address": row["address"],
                "brand": row["brand"],
                "operator": row["operator"],
                "opening_hours": row["opening_hours"],
                "phone": row["phone"],
                "website": row["website"],
            },
        )
        for row in rows
    ]
    return GeoJsonFeatureCollection(features=features)


@router.get("/layers/population", response_model=GeoJsonFeatureCollection)
def population_layer(
    session: Annotated[Session, Depends(get_session)],
    expected_release_id: int | None = None,
    west: Annotated[float, Query(ge=-180, le=180)] = 106.45,
    south: Annotated[float, Query(ge=-90, le=90)] = -6.38,
    east: Annotated[float, Query(ge=-180, le=180)] = 106.98,
    north: Annotated[float, Query(ge=-90, le=90)] = -5.60,
):
    _validate_bbox(west=west, south=south, east=east, north=north)
    release_id = active_release_id(session)
    if expected_release_id is not None and expected_release_id != release_id:
        raise HTTPException(
            status_code=409,
            detail={"code": "RELEASE_CHANGED", "message": "the active data release changed; reload the page"},
        )
    rows = session.execute(
        text(
            """
            SELECT
                id,
                name,
                population,
                population_density::float AS population_density,
                ST_AsGeoJSON(
                    ST_Multi(ST_SimplifyPreserveTopology(geom, 0.00003))
                )::json AS geometry
            FROM administrative_areas
            WHERE area_type = 'kelurahan'
              AND data_release_id = :release_id
              AND population_density IS NOT NULL
              AND geom && ST_MakeEnvelope(:west, :south, :east, :north, 4326)
            ORDER BY id
            """
        ),
        {
            "west": west,
            "south": south,
            "east": east,
            "north": north,
            "release_id": release_id,
        },
    ).mappings()
    return GeoJsonFeatureCollection(
        attribution="Satu Data Jakarta; © OpenStreetMap contributors",
        features=[
            GeoJsonFeature(
                id=row["id"],
                geometry=row["geometry"],
                properties={
                    "name": row["name"],
                    "population": row["population"],
                    "population_density": row["population_density"],
                },
            )
            for row in rows
        ],
    )


@router.get("/layers/points", response_model=GeoJsonFeatureCollection)
def point_layer(
    session: Annotated[Session, Depends(get_session)],
    layer: Literal[
        "transport", "commercial", "office", "education", "healthcare"
    ],
    west: Annotated[float, Query(ge=-180, le=180)] = 106.45,
    south: Annotated[float, Query(ge=-90, le=90)] = -6.38,
    east: Annotated[float, Query(ge=-180, le=180)] = 106.98,
    north: Annotated[float, Query(ge=-90, le=90)] = -5.60,
    limit: Annotated[int, Query(ge=1, le=10000)] = 5000,
):
    _validate_bbox(west=west, south=south, east=east, north=north)
    release_id = active_release_id(session)
    if layer == "transport":
        query = """
            SELECT id, name, transport_type AS item_type, source_record_id,
                   ST_AsGeoJSON(geom)::json AS geometry
            FROM transport_stops
            WHERE data_release_id = :release_id
              AND geom && ST_MakeEnvelope(:west, :south, :east, :north, 4326)
            ORDER BY id
            LIMIT :limit
        """
        attribution = "PT Transportasi Jakarta"
    else:
        poi_types = {
            "commercial": ["commercial"],
            "office": ["office"],
            "education": ["university", "college", "school"],
            "healthcare": ["hospital", "clinic", "doctors"],
        }[layer]
        query = """
            SELECT id, name, poi_type AS item_type, source_record_id,
                   ST_AsGeoJSON(ST_PointOnSurface(geom))::json AS geometry
            FROM pois
            WHERE data_release_id = :release_id
              AND poi_type = ANY(:poi_types)
              AND geom && ST_MakeEnvelope(:west, :south, :east, :north, 4326)
            ORDER BY id
            LIMIT :limit
        """
        attribution = "© OpenStreetMap contributors"
    parameters: dict[str, object] = {
        "west": west,
        "south": south,
        "east": east,
        "north": north,
        "limit": limit,
        "release_id": release_id,
    }
    if layer != "transport":
        parameters["poi_types"] = poi_types
    rows = session.execute(text(query), parameters).mappings()
    return GeoJsonFeatureCollection(
        attribution=attribution,
        features=[
            GeoJsonFeature(
                id=row["id"],
                geometry=row["geometry"],
                properties={
                    "name": row["name"],
                    "item_type": row["item_type"],
                    "source_record_id": row["source_record_id"],
                },
            )
            for row in rows
        ],
    )


@router.get("/layers/roads", response_model=GeoJsonFeatureCollection)
def road_layer(
    session: Annotated[Session, Depends(get_session)],
    west: Annotated[float, Query(ge=-180, le=180)] = 106.45,
    south: Annotated[float, Query(ge=-90, le=90)] = -6.38,
    east: Annotated[float, Query(ge=-180, le=180)] = 106.98,
    north: Annotated[float, Query(ge=-90, le=90)] = -5.60,
    limit: Annotated[int, Query(ge=1, le=20000)] = 10000,
):
    _validate_bbox(west=west, south=south, east=east, north=north)
    release_id = active_release_id(session)
    rows = session.execute(
        text(
            """
            SELECT id, name, road_type, source_record_id,
                   ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.00002))::json
                       AS geometry
            FROM roads
            WHERE data_release_id = :release_id
              AND geom && ST_MakeEnvelope(:west, :south, :east, :north, 4326)
            ORDER BY id
            LIMIT :limit
            """
        ),
        {
            "west": west,
            "south": south,
            "east": east,
            "north": north,
            "limit": limit,
            "release_id": release_id,
        },
    ).mappings()
    return GeoJsonFeatureCollection(
        features=[
            GeoJsonFeature(
                id=row["id"],
                geometry=row["geometry"],
                properties={
                    "name": row["name"],
                    "item_type": row["road_type"],
                    "source_record_id": row["source_record_id"],
                },
            )
            for row in rows
        ]
    )


@router.get("/poi", response_model=GeoJsonFeatureCollection)
def poi_alias(
    session: Annotated[Session, Depends(get_session)],
    poi_type: Annotated[
        Literal["transport", "commercial", "office", "education", "healthcare"],
        Query(alias="type"),
    ],
    west: Annotated[float, Query(ge=-180, le=180)] = 106.45,
    south: Annotated[float, Query(ge=-90, le=90)] = -6.38,
    east: Annotated[float, Query(ge=-180, le=180)] = 106.98,
    north: Annotated[float, Query(ge=-90, le=90)] = -5.60,
    limit: Annotated[int, Query(ge=1, le=10000)] = 5000,
):
    return point_layer(session, poi_type, west, south, east, north, limit)


@router.get("/areas", response_model=GeoJsonFeatureCollection)
def area_alias(
    session: Annotated[Session, Depends(get_session)],
    west: Annotated[float, Query(ge=-180, le=180)] = 106.45,
    south: Annotated[float, Query(ge=-90, le=90)] = -6.38,
    east: Annotated[float, Query(ge=-180, le=180)] = 106.98,
    north: Annotated[float, Query(ge=-90, le=90)] = -5.60,
):
    return population_layer(session, west, south, east, north)


@router.get(
    "/opportunity-map",
    response_model=GeoJsonFeatureCollection,
    responses={409: {"model": ApiError}},
)
def get_opportunity_map(
    session: Annotated[Session, Depends(get_session)],
    business_category: BusinessCategorySlug,
    radius_m: Annotated[int, Query()] = 1000,
    west: Annotated[float, Query(ge=-180, le=180)] = 106.45,
    south: Annotated[float, Query(ge=-90, le=90)] = -6.38,
    east: Annotated[float, Query(ge=-180, le=180)] = 106.98,
    north: Annotated[float, Query(ge=-90, le=90)] = -5.60,
):
    _validate_bbox(west=west, south=south, east=east, north=north)
    if radius_m not in SUPPORTED_RADII:
        raise HTTPException(status_code=422, detail="unsupported radius")
    try:
        return opportunity_map(
            session,
            category_slug=business_category,
            radius_m=radius_m,
            west=west,
            south=south,
            east=east,
            north=north,
        )
    except OpportunityScoresUnavailableError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "OPPORTUNITY_SCORES_UNAVAILABLE", "message": str(error)},
        ) from error


@router.get(
    "/area-rankings",
    response_model=AreaRankingResponse,
    responses={409: {"model": ApiError}},
)
def get_area_rankings(
    session: Annotated[Session, Depends(get_session)],
    business_category: BusinessCategorySlug,
    radius_m: Annotated[int, Query()] = 1000,
    limit: Annotated[int, Query(ge=1, le=267)] = 10,
):
    if radius_m not in SUPPORTED_RADII:
        raise HTTPException(status_code=422, detail="unsupported radius")
    try:
        return area_rankings(
            session,
            category_slug=business_category,
            radius_m=radius_m,
            limit=limit,
        )
    except OpportunityScoresUnavailableError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "OPPORTUNITY_SCORES_UNAVAILABLE", "message": str(error)},
        ) from error


@router.post(
    "/analyze-location",
    response_model=AnalyzeLocationResponse,
    responses={404: {"model": ApiError}, 409: {"model": ApiError}},
)
@router.post(
    "/analyze",
    response_model=AnalyzeLocationResponse,
    include_in_schema=False,
    responses={
        404: {"model": ApiError},
        409: {"model": ApiError},
    },
)
def analyze_location(
    request: AnalyzeLocationRequest,
    session: Annotated[Session, Depends(get_session)],
):
    try:
        return build_analysis_service(session).analyze(request)
    except LocationOutsideCoverageError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": error.code, "message": str(error)},
        ) from error
    except ScoringProfileUnavailableError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "SCORING_PROFILE_UNAVAILABLE", "message": str(error)},
        ) from error


@router.get(
    "/analytics",
    response_model=AnalyticsResponse,
    responses={409: {"model": ApiError}},
)
def get_analytics(
    session: Annotated[Session, Depends(get_session)],
    business_category: BusinessCategorySlug = "fnb",
    radius_m: int = 1000,
):
    if radius_m not in SUPPORTED_RADII:
        raise HTTPException(status_code=422, detail="unsupported radius")
    try:
        return analytics(
            session, category_slug=business_category, radius_m=radius_m
        )
    except LookupError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "ANALYTICS_UNAVAILABLE", "message": str(error)},
        ) from error


@router.get("/methodology", response_model=MethodologyResponse)
def get_methodology(session: Annotated[Session, Depends(get_session)]):
    return methodology(session)


@router.get("/search", response_model=list[SearchResult])
def search_locations(
    session: Annotated[Session, Depends(get_session)],
    q: Annotated[str, Query(min_length=2, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
):
    return search(session, query=q, limit=limit)


@router.get("/map-config", response_model=MapConfig)
def map_config(session: Annotated[Session, Depends(get_session)]) -> MapConfig:
    release = active_release(session)
    has_offline_tile = bool(release.tile_filename and release.tile_sha256)
    return MapConfig(
        release_id=release.id,
        release_key=release.release_key,
        taxonomy_version=release.taxonomy_version,
        tile_url=(
            f"/tiles/releases/{release.tile_filename}"
            if release.tile_filename
            else None
        ),
        tile_sha256=release.tile_sha256,
        bounds=(106.45, -6.38, 106.98, -5.60),
        min_zoom=7,
        max_zoom=15,
        attribution="© OpenStreetMap contributors",
        mode="offline" if has_offline_tile else "online_fallback",
        fallback_available=True,
    )


@router.get("/refresh-status", response_model=RefreshStatusResponse)
def refresh_status(
    session: Annotated[Session, Depends(get_session)],
) -> RefreshStatusResponse:
    active = active_release(session)
    pending = session.scalar(
        select(DataRelease)
        .where(DataRelease.status.in_(("staging", "validated")))
        .order_by(DataRelease.created_at.desc())
        .limit(1)
    )
    latest_failed = session.scalar(
        select(DataRelease)
        .where(DataRelease.status == "failed")
        .order_by(DataRelease.created_at.desc())
        .limit(1)
    )
    return RefreshStatusResponse(
        active=ReleaseSummary.model_validate(active, from_attributes=True),
        pending=(
            ReleaseSummary.model_validate(pending, from_attributes=True)
            if pending is not None
            else None
        ),
        latest_failed=(
            ReleaseSummary.model_validate(latest_failed, from_attributes=True)
            if latest_failed is not None
            else None
        ),
    )


@router.get("/datasets", response_model=list[DatasetSummary])
def datasets(session: Annotated[Session, Depends(get_session)]):
    release_id = active_release_id(session)
    rows = session.scalars(
        select(DatasetSource)
        .join(
            DataReleaseSource,
            DataReleaseSource.dataset_source_id == DatasetSource.id,
        )
        .where(DataReleaseSource.data_release_id == release_id)
        .order_by(DatasetSource.slug)
    ).all()
    return [DatasetSummary.model_validate(row, from_attributes=True) for row in rows]


@router.get("/metadata", response_model=MetadataResponse)
def metadata(session: Annotated[Session, Depends(get_session)]):
    release_id = active_release_id(session)
    datasets = session.scalars(
        select(DatasetSource)
        .join(
            DataReleaseSource,
            DataReleaseSource.dataset_source_id == DatasetSource.id,
        )
        .where(DataReleaseSource.data_release_id == release_id)
        .order_by(DatasetSource.slug)
    ).all()
    categories = session.scalars(
        select(BusinessCategory.slug)
        .where(BusinessCategory.is_active.is_(True))
        .order_by(BusinessCategory.id)
    ).all()
    return MetadataResponse(
        coverage="DKI Jakarta",
        categories=list(categories),
        supported_radii_m=[500, 1000, 2000, 3000, 5000],
        dataset_fingerprint=current_dataset_fingerprint(session),
        datasets=[DatasetSummary.model_validate(dataset, from_attributes=True) for dataset in datasets],
    )
