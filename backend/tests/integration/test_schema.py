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
