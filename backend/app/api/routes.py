import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.analysis.contracts import AnalyzeLocationRequest, AnalyzeLocationResponse
from app.analysis.service import LocationOutsideCoverageError, build_analysis_service
from app.api.contracts import (
    ApiError,
    CategorySummary,
    DatasetSummary,
    GeoJsonFeature,
    GeoJsonFeatureCollection,
    MetadataResponse,
)
from app.datasets.service import current_dataset_fingerprint
from app.db.models import Business, BusinessCategory, DatasetSource
from app.db.session import get_session
from app.scoring.service import ScoringProfileUnavailableError

router = APIRouter(prefix="/api")


def _validate_bbox(*, west: float, south: float, east: float, north: float) -> None:
    if west >= east or south >= north:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_BBOX", "message": "bbox bounds are inverted"},
        )


@router.get("/categories", response_model=list[CategorySummary])
def list_categories(session: Annotated[Session, Depends(get_session)]):
    rows = session.execute(
        select(
            BusinessCategory.slug,
            BusinessCategory.name,
            BusinessCategory.description,
            func.count(Business.id).label("business_count"),
        )
        .outerjoin(Business, Business.category_id == BusinessCategory.id)
        .where(BusinessCategory.is_active.is_(True))
        .group_by(BusinessCategory.id)
        .order_by(BusinessCategory.id)
    ).mappings()
    return [CategorySummary(**row) for row in rows]


@router.get("/businesses", response_model=GeoJsonFeatureCollection)
def list_businesses(
    session: Annotated[Session, Depends(get_session)],
    category: Literal["restaurant", "gym", "pharmacy"] | None = None,
    west: Annotated[float, Query(ge=-180, le=180)] = 106.68,
    south: Annotated[float, Query(ge=-90, le=90)] = -6.38,
    east: Annotated[float, Query(ge=-180, le=180)] = 106.98,
    north: Annotated[float, Query(ge=-90, le=90)] = -6.08,
    limit: Annotated[int, Query(ge=1, le=5000)] = 3000,
):
    _validate_bbox(west=west, south=south, east=east, north=north)
    rows = session.execute(
        text(
            """
            SELECT
                business.id,
                business.name,
                category.slug AS category,
                business.source_type,
                business.source_record_id,
                ST_AsGeoJSON(business.geom)::json AS geometry
            FROM businesses AS business
            JOIN business_categories AS category ON category.id = business.category_id
            WHERE (
                CAST(:category AS text) IS NULL
                OR category.slug = CAST(:category AS text)
            )
              AND business.geom && ST_MakeEnvelope(
                  :west, :south, :east, :north, 4326
              )
            ORDER BY business.id
            LIMIT :limit
            """
        ),
        {
            "category": category,
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
            },
        )
        for row in rows
    ]
    return GeoJsonFeatureCollection(features=features)


@router.get("/layers/population", response_model=GeoJsonFeatureCollection)
def population_layer(
    session: Annotated[Session, Depends(get_session)],
    west: Annotated[float, Query(ge=-180, le=180)] = 106.68,
    south: Annotated[float, Query(ge=-90, le=90)] = -6.38,
    east: Annotated[float, Query(ge=-180, le=180)] = 106.98,
    north: Annotated[float, Query(ge=-90, le=90)] = -6.08,
):
    _validate_bbox(west=west, south=south, east=east, north=north)
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
              AND population_density IS NOT NULL
              AND geom && ST_MakeEnvelope(:west, :south, :east, :north, 4326)
            ORDER BY id
            """
        ),
        {"west": west, "south": south, "east": east, "north": north},
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
    west: Annotated[float, Query(ge=-180, le=180)] = 106.68,
    south: Annotated[float, Query(ge=-90, le=90)] = -6.38,
    east: Annotated[float, Query(ge=-180, le=180)] = 106.98,
    north: Annotated[float, Query(ge=-90, le=90)] = -6.08,
    limit: Annotated[int, Query(ge=1, le=10000)] = 5000,
):
    _validate_bbox(west=west, south=south, east=east, north=north)
    if layer == "transport":
        query = """
            SELECT id, name, transport_type AS item_type, source_record_id,
                   ST_AsGeoJSON(geom)::json AS geometry
            FROM transport_stops
            WHERE geom && ST_MakeEnvelope(:west, :south, :east, :north, 4326)
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
            WHERE poi_type = ANY(:poi_types)
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


@router.post(
    "/analyze",
    response_model=AnalyzeLocationResponse,
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


@router.get("/metadata", response_model=MetadataResponse)
def metadata(session: Annotated[Session, Depends(get_session)]):
    datasets = session.scalars(
        select(DatasetSource).order_by(DatasetSource.slug)
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
