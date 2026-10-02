from fastapi.testclient import TestClient
from sqlalchemy import text

from app.datasets.service import current_dataset_fingerprint
from app.db.session import get_session
from app.main import app


def _client(db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    return TestClient(app)


def test_opportunity_map_and_rankings_use_exact_versioned_scope(db_session) -> None:
    source_id = db_session.scalar(
        text(
            """
            INSERT INTO dataset_sources (
                slug, provider, source_url, license_name, attribution,
                retrieved_at, sha256
            ) VALUES (
                'opportunity-test', 'Official Test Source',
                'https://example.test/opportunity', 'test-only', 'test-only',
                now(), repeat('e', 64)
            ) RETURNING id
            """
        )
    )
    area_ids = []
    for source_record_id, name, longitude in (
        ("area-a", "AREA A", 10.00),
        ("area-b", "AREA B", 10.12),
    ):
        area_ids.append(
            db_session.scalar(
                text(
                    """
                    INSERT INTO administrative_areas (
                        data_release_id, dataset_source_id, source_record_id, name, area_type,
                        population, population_density, retrieved_at,
                        original_properties, geom
                    ) VALUES (
                        (SELECT id FROM data_releases WHERE status = 'active'),
                        :source_id, :source_record_id, :name, 'kelurahan',
                        12000, 15000, now(), '{}'::jsonb,
                        ST_Multi(ST_MakeEnvelope(
                            :longitude, 10, :longitude + 0.08, 10.08, 4326
                        ))
                    ) RETURNING id
                    """
                ),
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "name": name,
                    "longitude": longitude,
                },
            )
        )
    category_id = db_session.scalar(
        text("SELECT id FROM business_categories WHERE slug = 'gym'")
    )
    fingerprint = current_dataset_fingerprint(db_session)
    for area_id, score, label in (
        (area_ids[0], 72.0, "Good"),
        (area_ids[1], 88.0, "High"),
    ):
        db_session.execute(
            text(
                """
                INSERT INTO opportunity_scores (
                    data_release_id, administrative_area_id, category_id, radius_m,
                    dataset_fingerprint, scoring_version, final_score, label,
                    raw_factors, normalized_factors
                ) VALUES (
                    (SELECT id FROM data_releases WHERE status = 'active'),
                    :area_id, :category_id, 1000, :fingerprint, 'v1.0.0',
                    :score, :label, '{"competition": 2}'::jsonb,
                    jsonb_build_object('competition', :score)
                )
                """
            ),
            {
                "area_id": area_id,
                "category_id": category_id,
                "fingerprint": fingerprint,
                "score": score,
                "label": label,
            },
        )

    client = _client(db_session)
    try:
        ranking_response = client.get(
            "/api/area-rankings",
            params={"business_category": "gym", "radius_m": 1000, "limit": 2},
        )
        map_response = client.get(
            "/api/opportunity-map",
            params={
                "business_category": "gym",
                "radius_m": 1000,
                "west": 9.9,
                "south": 9.9,
                "east": 10.3,
                "north": 10.2,
            },
        )
        partial_map_response = client.get(
            "/api/opportunity-map",
            params={
                "business_category": "gym",
                "radius_m": 1000,
                "west": 9.99,
                "south": 9.99,
                "east": 10.09,
                "north": 10.09,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert ranking_response.status_code == 200
    ranking = ranking_response.json()
    assert [item["area_name"] for item in ranking["items"]] == ["AREA B", "AREA A"]
    assert [item["rank"] for item in ranking["items"]] == [1, 2]
    assert ranking["dataset_fingerprint"] == fingerprint
    assert ranking["items"][0]["representative_method"] == "point_on_surface"

    assert map_response.status_code == 200
    features = map_response.json()["features"]
    assert [feature["properties"]["final_score"] for feature in features] == [88.0, 72.0]
    assert all(feature["geometry"]["type"] == "MultiPolygon" for feature in features)
    assert partial_map_response.status_code == 200
    assert partial_map_response.json()["features"][0]["properties"]["rank"] == 2


def test_rankings_reject_unsupported_radius(db_session) -> None:
    try:
        response = _client(db_session).get(
            "/api/area-rankings",
            params={"business_category": "restaurant", "radius_m": 750},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
