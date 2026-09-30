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
    if west >= east or south >= north:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_BBOX", "message": "bbox bounds are inverted"},
        )
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
