from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import (
    BusinessCategory,
    DataRelease,
    DataReleaseSource,
    DatasetSource,
)
from app.db.session import get_session
from app.core.config import Settings, get_settings
from app.main import app
from app.releases.service import activate_release, create_staging_release


def _client(session: Session) -> TestClient:
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def _activate_v2(session: Session) -> DataRelease:
    release = create_staging_release(
        session,
        {
            "release_key": "api-v2-release",
            "dataset_fingerprint": "7" * 64,
            "taxonomy_version": "v2.0.0",
            "scoring_version": "v2.0.0",
        },
    )
    release.status = "validated"
    release.tile_filename = "api-v2-release.pmtiles"
    release.tile_sha256 = "8" * 64
    session.flush()
    activate_release(session, release.id)
    return release


def test_v2_categories_and_business_geojson_are_strict(db_session: Session) -> None:
    release = _activate_v2(db_session)
    source = DatasetSource(
        slug="api-v2-osm",
        provider="OpenStreetMap",
        source_url="https://www.openstreetmap.org",
        license_name="ODbL-1.0",
        attribution="© OpenStreetMap contributors",
        observed_at=None,
        retrieved_at=datetime.now(UTC),
        sha256="9" * 64,
    )
    db_session.add(source)
    db_session.flush()
    fnb_id = db_session.scalar(
        select(BusinessCategory.id).where(BusinessCategory.slug == "fnb")
    )
    db_session.execute(
        text(
            """
            INSERT INTO businesses (
                data_release_id, category_id, dataset_source_id, name,
                source_type, source_record_id, business_subtype,
                taxonomy_version, retrieved_at, original_tags, geom
            ) VALUES (
                :release_id, :category_id, :source_id, 'API V2 Cafe',
                'node', 'V2-1', 'cafe', 'v2.0.0', now(),
                '{"brand":"Brand Nyata","phone":"021-123","addr:street":"Jalan Test"}'::jsonb,
                ST_SetSRID(ST_Point(106.8, -6.2), 4326)
            )
            """
        ),
        {"release_id": release.id, "category_id": fnb_id, "source_id": source.id},
    )

    client = _client(db_session)
    try:
        categories = client.get("/api/business-categories")
        businesses = client.get(
            "/api/businesses",
            params={
                "category": "fnb",
                "west": 106.7,
                "south": -6.3,
                "east": 106.9,
                "north": -6.1,
            },
        )
        old_category = client.get("/api/businesses", params={"category": "restaurant"})
    finally:
        app.dependency_overrides.clear()

    assert categories.status_code == 200
    assert [item["slug"] for item in categories.json()] == ["fnb", "retail", "services"]
    assert businesses.status_code == 200
    feature = businesses.json()["features"][0]
    assert feature["properties"]["business_subtype"] == "cafe"
    assert feature["properties"]["brand"] == "Brand Nyata"
    assert feature["properties"]["operator"] is None
    assert feature["properties"]["source_record_id"] == "V2-1"
    assert old_category.status_code == 422


def test_map_config_and_refresh_status_use_active_release(db_session: Session) -> None:
    release = _activate_v2(db_session)
    client = _client(db_session)
    try:
        map_response = client.get("/api/map-config")
        status_response = client.get("/api/refresh-status")
    finally:
        app.dependency_overrides.clear()

    assert map_response.status_code == 200
    map_config = map_response.json()
    assert map_config["release_id"] == release.id
    assert map_config["tile_url"].endswith("api-v2-release.pmtiles")
    assert map_config["tile_sha256"] == "8" * 64
    assert map_config["mode"] == "offline"

    assert status_response.status_code == 200
    status = status_response.json()
    assert status["active"]["release_key"] == release.release_key
    assert "trigger_url" not in status


def test_active_pmtiles_artifact_supports_byte_ranges(
    db_session: Session, tmp_path: Path
) -> None:
    release = _activate_v2(db_session)
    artifact = tmp_path / str(release.tile_filename)
    artifact.write_bytes(b"PMTiles\x03" + b"vector archive")
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_settings] = lambda: Settings(tile_root=tmp_path)
    client = TestClient(app)
    try:
        response = client.get(
            f"/tiles/releases/{release.tile_filename}",
            headers={"Range": "bytes=0-7"},
        )
        hidden = client.get("/tiles/releases/not-active.pmtiles")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 206
    assert response.content == b"PMTiles\x03"
    assert response.headers["accept-ranges"] == "bytes"
    assert hidden.status_code == 404


def test_v2_analytics_and_methodology_are_release_scoped(db_session: Session) -> None:
    release = _activate_v2(db_session)
    source = DatasetSource(
        slug="api-v2-analytics",
        provider="OpenStreetMap",
        source_url="https://www.openstreetmap.org",
        license_name="ODbL-1.0",
        attribution="© OpenStreetMap contributors",
        observed_at=None,
        retrieved_at=datetime.now(UTC),
        sha256="a" * 64,
    )
    db_session.add(source)
    db_session.flush()
    db_session.add(
        DataReleaseSource(
            data_release_id=release.id,
            dataset_source_id=source.id,
            role="businesses",
        )
    )
    category_id = db_session.scalar(
        select(BusinessCategory.id).where(BusinessCategory.slug == "fnb")
    )
    area_id = db_session.scalar(
        text(
            """
            INSERT INTO administrative_areas (
                data_release_id, dataset_source_id, source_record_id, name,
                area_type, population, population_density, retrieved_at,
                original_properties, geom
            ) VALUES (
                :release_id, :source_id, 'v2-area', 'AREA V2', 'kelurahan',
                10000, 12000, now(), '{}'::jsonb,
                ST_Multi(ST_MakeEnvelope(106.79, -6.21, 106.81, -6.19, 4326))
            ) RETURNING id
            """
        ),
        {"release_id": release.id, "source_id": source.id},
    )
    db_session.execute(
        text(
            """
            INSERT INTO businesses (
                data_release_id, category_id, dataset_source_id, name,
                source_type, source_record_id, business_subtype,
                taxonomy_version, retrieved_at, original_tags, geom
            ) VALUES
                (:release_id, :category_id, :source_id, 'Cafe V2', 'node',
                 'v2-cafe', 'cafe', 'v2.0.0', now(), '{}'::jsonb,
                 ST_SetSRID(ST_Point(106.8, -6.2), 4326)),
                (:release_id, :category_id, :source_id, 'Bakery V2', 'node',
                 'v2-bakery', 'bakery', 'v2.0.0', now(), '{}'::jsonb,
                 ST_SetSRID(ST_Point(106.801, -6.201), 4326))
            """
        ),
        {
            "release_id": release.id,
            "category_id": category_id,
            "source_id": source.id,
        },
    )
    db_session.execute(
        text(
            """
            INSERT INTO opportunity_scores (
                data_release_id, administrative_area_id, category_id, radius_m,
                dataset_fingerprint, scoring_version, final_score, label,
                raw_factors, normalized_factors
            ) VALUES (
                :release_id, :area_id, :category_id, 1000,
                :fingerprint, 'v2.0.0', 84, 'High',
                jsonb_build_object('population_density', 12000, 'competition', 2),
                jsonb_build_object('population_density', 80, 'competition', 70)
            )
            """
        ),
        {
            "release_id": release.id,
            "area_id": area_id,
            "category_id": category_id,
            "fingerprint": release.dataset_fingerprint,
        },
    )

    client = _client(db_session)
    try:
        analytics = client.get(
            "/api/analytics",
            params={"business_category": "fnb", "radius_m": 1000},
        )
        methodology = client.get("/api/methodology")
    finally:
        app.dependency_overrides.clear()

    assert analytics.status_code == 200
    analytics_body = analytics.json()
    assert analytics_body["release_key"] == release.release_key
    assert analytics_body["taxonomy_version"] == "v2.0.0"
    assert analytics_body["subtype_counts"] == [
        {"subtype": "bakery", "count": 1},
        {"subtype": "cafe", "count": 1},
    ]

    assert methodology.status_code == 200
    methodology_body = methodology.json()
    assert methodology_body["release_key"] == release.release_key
    assert methodology_body["tile_sha256"] == "8" * 64
    assert methodology_body["datasets"][0]["sha256"] == "a" * 64
    assert {item["category"] for item in methodology_body["categories"]} == {
        "fnb",
        "retail",
        "services",
    }
    assert {
        (item["category"], item["subtype"])
        for item in methodology_body["taxonomy_rules"]
    } >= {("fnb", "restaurant"), ("retail", "supermarket"), ("services", "gym")}
