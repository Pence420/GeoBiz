from sqlalchemy import text


def test_every_demo_business_is_traceable_and_spatially_valid(db_session) -> None:
    invalid_count = db_session.scalar(
        text(
            """
            SELECT count(*) FROM businesses
            WHERE data_release_id = (
                    SELECT id FROM data_releases WHERE status = 'active'
                  )
              AND (dataset_source_id IS NULL
               OR source_record_id IS NULL
               OR retrieved_at IS NULL
               OR ST_IsValid(geom) = false
               OR ST_IsEmpty(geom))
            """
        )
    )
    assert invalid_count == 0


def test_demo_database_has_no_synthetic_provider(db_session) -> None:
    count = db_session.scalar(
        text(
            """
            SELECT count(*)
            FROM dataset_sources AS source
            JOIN data_release_sources AS link
              ON link.dataset_source_id = source.id
            JOIN data_releases AS release
              ON release.id = link.data_release_id
            WHERE release.status = 'active'
              AND lower(source.provider) IN ('fake', 'fixture', 'synthetic', 'seed')
            """
        )
    )
    assert count == 0


def test_all_supported_categories_have_real_coverage(db_session) -> None:
    rows = db_session.execute(
        text(
            """
                SELECT category.slug, count(business.id)
                FROM business_categories AS category
                LEFT JOIN businesses AS business
                  ON business.category_id = category.id
                 AND business.data_release_id = (
                    SELECT id FROM data_releases WHERE status = 'active'
                 )
                WHERE category.is_active = true
            GROUP BY category.slug
            ORDER BY category.slug
            """
        )
    ).all()
    assert dict(rows) == {"gym": 53, "pharmacy": 305, "restaurant": 1826}


def test_population_and_opportunity_coverage_is_complete(db_session) -> None:
    populated_areas = db_session.scalar(
        text(
            """
            SELECT count(*) FROM administrative_areas
            WHERE data_release_id = (
                    SELECT id FROM data_releases WHERE status = 'active'
                  )
              AND area_type = 'kelurahan' AND population_density IS NOT NULL
            """
        )
    )
    opportunity_scopes = db_session.execute(
        text(
            """
            SELECT count(*)
            FROM (
                SELECT category_id, radius_m
                FROM opportunity_scores
                WHERE data_release_id = (
                    SELECT id FROM data_releases WHERE status = 'active'
                )
                GROUP BY category_id, radius_m
                HAVING count(*) = 267
            ) AS complete_scopes
            """
        )
    ).scalar_one()
    assert populated_areas == 267
    assert opportunity_scopes == 15
