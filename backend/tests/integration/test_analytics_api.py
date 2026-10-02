from fastapi.testclient import TestClient
from sqlalchemy import text

from app.datasets.service import current_dataset_fingerprint
from app.db.session import get_session
from app.main import app
from app.releases.service import activate_release, create_staging_release


def _client(db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    return TestClient(app)


def _seed_search_and_score_scope(db_session) -> None:
    release = create_staging_release(
        db_session,
        {
            "release_key": "analytics-v2-test",
            "dataset_fingerprint": "f" * 64,
            "taxonomy_version": "v2.0.0",
            "scoring_version": "v2.0.0",
        },
    )
    release.status = "validated"
    release.tile_filename = "analytics-v2-test.pmtiles"
    release.tile_sha256 = "e" * 64
    db_session.flush()
    activate_release(db_session, release.id)
    source_id = db_session.scalar(
        text(
            """
            INSERT INTO dataset_sources (
                slug, provider, source_url, license_name, attribution,
                observed_at, retrieved_at, sha256
            ) VALUES (
                'analytics-test', 'Official Analytics Test',
                'https://example.test/analytics', 'test-only', 'test-only',
                DATE '2025-01-01', now(), repeat('f', 64)
            ) RETURNING id
            """
        )
    )
    db_session.execute(
        text(
            """
            INSERT INTO data_release_sources (
                data_release_id, dataset_source_id, role
            ) VALUES (:release_id, :source_id, 'businesses')
            """
        ),
        {"release_id": release.id, "source_id": source_id},
    )
    area_id = db_session.scalar(
        text(
            """
            INSERT INTO administrative_areas (
                data_release_id, dataset_source_id, source_record_id, name, area_type,
                population, population_density, retrieved_at,
                original_properties, geom
            ) VALUES (
                (SELECT id FROM data_releases WHERE status = 'active'),
                :source_id, 'senayan-test', 'SENAYAN TEST', 'kelurahan',
                10000, 12500, now(), '{}'::jsonb,
                ST_Multi(ST_MakeEnvelope(106.79, -6.23, 106.81, -6.21, 4326))
            ) RETURNING id
            """
        ),
        {"source_id": source_id},
    )
    db_session.execute(
        text(
            """
            INSERT INTO administrative_areas (
                data_release_id, dataset_source_id, source_record_id, official_code,
                name, area_type, retrieved_at, original_properties, geom
            ) VALUES (
                (SELECT id FROM data_releases WHERE status = 'active'),
                :source_id, 'dki-test', 'ID-JK', 'DKI JAKARTA', 'province',
                now(), '{}'::jsonb,
                ST_Multi(ST_MakeEnvelope(106.75, -6.27, 106.85, -6.17, 4326))
            )
            """
        ),
        {"source_id": source_id},
    )
    category_id = db_session.scalar(
        text("SELECT id FROM business_categories WHERE slug = 'fnb'")
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
                :category_id, :source_id, 'Senayan Test Restaurant', 'node',
                'restaurant-test', 'restaurant', 'v2.0.0', now(), '{}'::jsonb,
                ST_SetSRID(ST_Point(106.8, -6.22), 4326)
            )
            """
        ),
        {"category_id": category_id, "source_id": source_id},
    )
    db_session.execute(
        text(
            """
            INSERT INTO pois (
                data_release_id, dataset_source_id, name, poi_type, source_type,
                source_record_id, retrieved_at, original_tags, geom
            ) VALUES (
                (SELECT id FROM data_releases WHERE status = 'active'),
                :source_id, 'Senayan Test Landmark', 'commercial', 'node',
                'landmark-test', now(), '{}'::jsonb,
                ST_SetSRID(ST_Point(106.801, -6.221), 4326)
            )
            """
        ),
        {"source_id": source_id},
    )
    fingerprint = current_dataset_fingerprint(db_session)
    db_session.execute(
        text(
            """
            INSERT INTO opportunity_scores (
                data_release_id, administrative_area_id, category_id, radius_m,
                dataset_fingerprint, scoring_version, final_score, label,
                raw_factors, normalized_factors
            ) VALUES (
                (SELECT id FROM data_releases WHERE status = 'active'),
                :area_id, :category_id, 1000, :fingerprint, 'v2.0.0',
                82, 'High',
                '{"population_density": 12500, "competition": 1}'::jsonb,
                '{"population_density": 80, "competition": 75}'::jsonb
            )
            """
        ),
        {
            "area_id": area_id,
            "category_id": category_id,
            "fingerprint": fingerprint,
        },
    )


def test_analytics_and_methodology_expose_definitions_and_provenance(db_session) -> None:
    _seed_search_and_score_scope(db_session)
    client = _client(db_session)
    try:
        analytics_response = client.get(
            "/api/analytics",
            params={"business_category": "fnb", "radius_m": 1000},
        )
        methodology_response = client.get("/api/methodology")
    finally:
        app.dependency_overrides.clear()

    assert analytics_response.status_code == 200
    analytics_payload = analytics_response.json()
    assert analytics_payload["top_opportunities"][0]["area_name"] == "SENAYAN TEST"
    assert analytics_payload["top_opportunities"][0]["final_score"] == 82.0
    assert sum(item["area_count"] for item in analytics_payload["score_distribution"]) == 1
    assert all(item["definition"] for item in analytics_payload["coverage"])

    assert methodology_response.status_code == 200
    methodology_payload = methodology_response.json()
    assert methodology_payload["scoring_version"] == "v2.0.0"
    assert methodology_payload["taxonomy_version"] == "v2.0.0"
    assert methodology_payload["release_key"] == "analytics-v2-test"
    assert len(methodology_payload["categories"]) == 3
    assert methodology_payload["factor_definitions"]["competition"]
    assert any("does not predict" in item for item in methodology_payload["limitations"])


def test_search_supports_area_business_landmark_and_coordinate(db_session) -> None:
    _seed_search_and_score_scope(db_session)
    client = _client(db_session)
    try:
        text_response = client.get("/api/search", params={"q": "Senayan Test"})
        coordinate_response = client.get(
            "/api/search", params={"q": "-6.2200, 106.8000"}
        )
    finally:
        app.dependency_overrides.clear()

    assert text_response.status_code == 200
    assert {item["result_type"] for item in text_response.json()} == {
        "area",
        "business",
        "landmark",
    }
    assert coordinate_response.status_code == 200
    assert coordinate_response.json()[0]["result_type"] == "coordinate"


def test_prd_endpoint_aliases_are_available(db_session) -> None:
    _seed_search_and_score_scope(db_session)
    client = _client(db_session)
    try:
        categories = client.get("/api/business-categories")
        areas = client.get(
            "/api/areas",
            params={"west": 106.78, "south": -6.24, "east": 106.82, "north": -6.2},
        )
        pois = client.get(
            "/api/poi",
            params={
                "type": "commercial",
                "west": 106.78,
                "south": -6.24,
                "east": 106.82,
                "north": -6.2,
            },
        )
        analysis = client.post(
            "/api/analyze-location",
            json={
                "latitude": -6.22,
                "longitude": 106.8,
                "business_category": "fnb",
                "radius": 1000,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert categories.status_code == 200
    assert areas.status_code == 200
    assert pois.status_code == 200
    assert analysis.status_code in {200, 409}
