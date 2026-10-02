from sqlalchemy import text

from app.analysis.repository import SpatialRepository


def _seed_source(db_session, slug: str) -> int:
    return db_session.scalar(
        text(
            """
            INSERT INTO dataset_sources (
                slug, provider, source_url, license_name, attribution,
                retrieved_at, sha256
            ) VALUES (
                :slug, 'test', 'https://example.test', 'test-only',
                'test-only', now(), repeat('a', 64)
            ) RETURNING id
            """
        ),
        {"slug": slug},
    )


def test_radius_includes_point_on_boundary(db_session) -> None:
    source_id = _seed_source(db_session, "test-radius-source")
    category_id = db_session.scalar(
        text("SELECT id FROM business_categories WHERE slug='restaurant'")
    )
    db_session.execute(
        text(
            """
            INSERT INTO businesses (
                data_release_id, category_id, dataset_source_id, name, source_type,
                source_record_id, business_subtype, taxonomy_version,
                retrieved_at, original_tags, geom
            ) VALUES
                ((SELECT id FROM data_releases WHERE status = 'active'),
                 :category_id, :source_id, 'exactly 1km', 'node', 'edge',
                 'restaurant', 'v1.0.0', now(),
                 '{}'::jsonb,
                 ST_Project(ST_SetSRID(ST_Point(0, 0), 4326)::geography,
                            1000, radians(90))::geometry),
                ((SELECT id FROM data_releases WHERE status = 'active'),
                 :category_id, :source_id, 'outside 1km', 'node', 'outside',
                 'restaurant', 'v1.0.0', now(),
                 '{}'::jsonb,
                 ST_Project(ST_SetSRID(ST_Point(0, 0), 4326)::geography,
                            1001, radians(90))::geometry)
            """
        ),
        {"category_id": category_id, "source_id": source_id},
    )

    metrics = SpatialRepository(db_session).calculate_metrics(
        longitude=0, latitude=0, category_slug="restaurant", radius_m=1000
    )

    assert metrics.competitor_count == 1


def test_st_covers_includes_administrative_boundary_edge(db_session) -> None:
    source_id = _seed_source(db_session, "test-boundary-source")
    db_session.execute(
        text(
            """
            INSERT INTO administrative_areas (
                data_release_id, dataset_source_id, source_record_id, official_code, name,
                area_type, retrieved_at, original_properties, geom
            ) VALUES (
                (SELECT id FROM data_releases WHERE status = 'active'),
                :source_id, 'test/1', 'TEST', 'Test Coverage', 'province', now(),
                '{}'::jsonb,
                ST_Multi(ST_GeomFromText(
                    'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))', 4326
                ))
            )
            """
        ),
        {"source_id": source_id},
    )
    repository = SpatialRepository(db_session)

    area = repository.find_containing_area(longitude=0, latitude=0.5)

    assert area is not None
    assert area.official_code == "TEST"
    assert repository.find_containing_area(longitude=2, latitude=2) is None
