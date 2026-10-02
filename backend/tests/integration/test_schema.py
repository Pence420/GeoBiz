import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session


def test_spatial_schema_has_provenance_and_gist_indexes(db_session: Session) -> None:
    extension = db_session.scalar(
        text("SELECT extname FROM pg_extension WHERE extname = 'postgis'")
    )
    business_columns = {
        row[0]
        for row in db_session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'businesses'
                """
            )
        )
    }
    indexes = {
        row[0]
        for row in db_session.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = 'businesses'
                """
            )
        )
    }

    assert extension == "postgis"
    assert {"dataset_source_id", "source_record_id", "retrieved_at", "geom"} <= business_columns
    assert "ix_businesses_geom_gist" in indexes


def test_all_foreign_keys_are_indexed(db_session: Session) -> None:
    missing_indexes = db_session.execute(
        text(
            """
            SELECT conrelid::regclass::text AS table_name, a.attname AS column_name
            FROM pg_constraint c
            JOIN pg_attribute a
              ON a.attrelid = c.conrelid
             AND a.attnum = ANY(c.conkey)
            WHERE c.contype = 'f'
              AND c.connamespace = 'public'::regnamespace
              AND NOT EXISTS (
                SELECT 1
                FROM pg_index i
                WHERE i.indrelid = c.conrelid
                  AND a.attnum = ANY(i.indkey)
              )
            """
        )
    ).all()

    assert missing_indexes == []


def test_v1_scoring_weights_sum_to_one_per_category(db_session: Session) -> None:
    rows = db_session.execute(
        text(
            """
            SELECT category.slug, sum(scoring.weight)::float AS total_weight
            FROM scoring_weights AS scoring
            JOIN business_categories AS category ON category.id = scoring.category_id
            WHERE scoring.version = 'v1.0.0'
            GROUP BY category.slug
            ORDER BY category.slug
            """
        )
    ).all()

    assert [slug for slug, _ in rows] == ["gym", "pharmacy", "restaurant"]
    assert all(total == pytest.approx(1.0) for _, total in rows)


def test_v2_scoring_weights_match_the_approved_spec(db_session: Session) -> None:
    rows = db_session.execute(
        text(
            """
            SELECT category.slug, scoring.factor_name, scoring.weight::float,
                   scoring.is_required
            FROM scoring_weights AS scoring
            JOIN business_categories AS category ON category.id = scoring.category_id
            WHERE scoring.version = 'v2.0.0'
            ORDER BY category.slug, scoring.factor_name
            """
        )
    ).all()
    actual = {
        (category, factor): (weight, required)
        for category, factor, weight, required in rows
    }
    expected = {
        "fnb": {
            "population_density": 0.20,
            "competition": 0.20,
            "public_transport": 0.15,
            "commercial_activity": 0.15,
            "office_activity": 0.20,
            "road_accessibility": 0.10,
            "healthcare_proximity": 0.00,
        },
        "retail": {
            "population_density": 0.25,
            "competition": 0.20,
            "public_transport": 0.15,
            "commercial_activity": 0.20,
            "office_activity": 0.10,
            "road_accessibility": 0.10,
            "healthcare_proximity": 0.00,
        },
        "services": {
            "population_density": 0.25,
            "competition": 0.20,
            "public_transport": 0.10,
            "commercial_activity": 0.15,
            "office_activity": 0.15,
            "road_accessibility": 0.15,
            "healthcare_proximity": 0.00,
        },
    }

    assert len(actual) == 21
    for category, factors in expected.items():
        assert sum(actual[(category, factor)][0] for factor in factors) == pytest.approx(1)
        for factor, weight in factors.items():
            assert actual[(category, factor)][0] == pytest.approx(weight)
            assert actual[(category, factor)][1] is (weight > 0)


def test_opportunity_scores_have_scope_constraints_and_lookup_index(
    db_session: Session,
) -> None:
    columns = {
        row[0]
        for row in db_session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'opportunity_scores'
                """
            )
        )
    }
    indexes = {
        row[0]
        for row in db_session.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'opportunity_scores'
                """
            )
        )
    }

    assert {
        "administrative_area_id",
        "category_id",
        "radius_m",
        "dataset_fingerprint",
        "scoring_version",
        "final_score",
        "normalized_factors",
    } <= columns
    assert "ix_opportunity_scores_lookup" in indexes
