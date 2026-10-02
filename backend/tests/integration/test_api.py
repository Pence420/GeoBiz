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
                data_release_id, category_id, dataset_source_id, name, source_type,
                source_record_id, business_subtype, taxonomy_version,
                retrieved_at, original_tags, geom
            ) VALUES (
                (SELECT id FROM data_releases WHERE status = 'active'),
                :category_id, :source_id, 'API Test Restaurant', 'node',
                '987654321', 'restaurant', 'v1.0.0', now(),
                '{"name":"API Test Restaurant"}'::jsonb,
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


def test_population_layer_returns_real_area_geometry(db_session) -> None:
    source_id = db_session.scalar(
        text(
            """
            INSERT INTO dataset_sources (
                slug, provider, source_url, license_name, attribution,
                retrieved_at, sha256
            ) VALUES (
                'layer-test', 'Official Test Source', 'https://example.test/layer',
                'test-only', 'test-only', now(), repeat('c', 64)
            ) RETURNING id
            """
        )
    )
    db_session.execute(
        text(
            """
            INSERT INTO administrative_areas (
                data_release_id, dataset_source_id, source_record_id, name, area_type,
                population, population_density, retrieved_at,
                original_properties, geom
            ) VALUES (
                (SELECT id FROM data_releases WHERE status = 'active'),
                :source_id, 'layer-area', 'LAYER TEST AREA', 'kelurahan',
                12000, 15000, now(), '{}'::jsonb,
                ST_Multi(ST_GeomFromText(
                    'POLYGON((10 10, 10.1 10, 10.1 10.1, 10 10.1, 10 10))',
                    4326
                ))
            )
            """
        ),
        {"source_id": source_id},
    )

    try:
        response = _client(db_session).get(
            "/api/layers/population",
            params={"west": 9.9, "south": 9.9, "east": 10.2, "north": 10.2},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    feature = response.json()["features"][0]
    assert feature["properties"] == {
        "name": "LAYER TEST AREA",
        "population": 12000,
        "population_density": 15000.0,
    }
    assert feature["geometry"]["type"] == "MultiPolygon"


def test_transport_layer_preserves_source_record_identity(db_session) -> None:
    source_id = db_session.scalar(
        text(
            """
            INSERT INTO dataset_sources (
                slug, provider, source_url, license_name, attribution,
                retrieved_at, sha256
            ) VALUES (
                'transport-layer-test', 'Official Test Source',
                'https://example.test/transport', 'test-only', 'test-only',
                now(), repeat('d', 64)
            ) RETURNING id
            """
        )
    )
    db_session.execute(
        text(
            """
            INSERT INTO transport_stops (
                data_release_id, dataset_source_id, name, transport_type, source_record_id,
                retrieved_at, original_properties, geom
            ) VALUES (
                (SELECT id FROM data_releases WHERE status = 'active'),
                :source_id, 'Layer Test Stop', 'bus', 'STOP-REAL-1',
                now(), '{}'::jsonb, ST_SetSRID(ST_Point(10.05, 10.05), 4326)
            )
            """
        ),
        {"source_id": source_id},
    )

    try:
        response = _client(db_session).get(
            "/api/layers/points",
            params={
                "layer": "transport",
                "west": 10,
                "south": 10,
                "east": 10.1,
                "north": 10.1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    feature = response.json()["features"][0]
    assert feature["properties"]["name"] == "Layer Test Stop"
    assert feature["properties"]["source_record_id"] == "STOP-REAL-1"
