from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import get_session
from app.main import app


def _client(db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    return TestClient(app)


def test_businesses_returns_real_source_identity_as_geojson(db_session) -> None:
    source_id = db_session.scalar(
        text(
            """
            INSERT INTO dataset_sources (
                slug, provider, source_url, license_name, attribution,
                retrieved_at, sha256
            ) VALUES (
                'api-test', 'OpenStreetMap', 'https://www.openstreetmap.org',
                'ODbL', '© OpenStreetMap contributors', now(), repeat('b', 64)
            ) RETURNING id
            """
        )
    )
    category_id = db_session.scalar(
        text("SELECT id FROM business_categories WHERE slug = 'restaurant'")
    )
    db_session.execute(
        text(
            """
            INSERT INTO businesses (
                category_id, dataset_source_id, name, source_type,
                source_record_id, retrieved_at, original_tags, geom
            ) VALUES (
                :category_id, :source_id, 'API Test Restaurant', 'node',
                '987654321', now(), '{"name":"API Test Restaurant"}'::jsonb,
                ST_SetSRID(ST_Point(106.82, -6.18), 4326)
            )
            """
        ),
        {"category_id": category_id, "source_id": source_id},
    )

    try:
        response = _client(db_session).get(
            "/api/businesses",
            params={
                "category": "restaurant",
                "west": 106.81,
                "south": -6.19,
                "east": 106.83,
                "north": -6.17,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    feature = next(
        item for item in payload["features"]
        if item["properties"]["source_record_id"] == "987654321"
    )
    assert feature["properties"]["name"] == "API Test Restaurant"
    assert feature["geometry"] == {"type": "Point", "coordinates": [106.82, -6.18]}
    assert payload["attribution"] == "© OpenStreetMap contributors"


def test_businesses_rejects_inverted_bbox(db_session) -> None:
    try:
        response = _client(db_session).get(
            "/api/businesses",
            params={"west": 107, "east": 106, "south": -6.3, "north": -6.1},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_BBOX"


def test_analyze_rejects_location_outside_dki(db_session) -> None:
    try:
        response = _client(db_session).post(
            "/api/analyze",
            json={
                "latitude": 0,
                "longitude": 0,
                "business_category": "gym",
                "radius_m": 1000,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "LOCATION_OUTSIDE_COVERAGE"
