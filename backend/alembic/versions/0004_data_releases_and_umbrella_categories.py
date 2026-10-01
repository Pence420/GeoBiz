"""Add immutable data releases and umbrella-category storage.

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


RELEASE_BOUND_TABLES = (
    "administrative_areas",
    "businesses",
    "pois",
    "transport_stops",
    "roads",
    "normalization_profiles",
    "opportunity_scores",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE data_releases (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            release_key text NOT NULL,
            status text NOT NULL,
            dataset_fingerprint text NOT NULL,
            taxonomy_version text NOT NULL,
            scoring_version text NOT NULL,
            combined_manifest jsonb NOT NULL,
            tile_filename text,
            tile_sha256 text,
            failure jsonb,
            validated_at timestamptz,
            activated_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_data_releases_release_key UNIQUE (release_key),
            CONSTRAINT ck_data_releases_status CHECK (
                status IN ('staging', 'validated', 'active', 'superseded', 'failed')
            )
        );

        CREATE UNIQUE INDEX uq_data_releases_single_active
            ON data_releases (status)
            WHERE status = 'active';
        CREATE UNIQUE INDEX uq_data_releases_single_prepared
            ON data_releases ((1))
            WHERE status IN ('staging', 'validated');

        INSERT INTO data_releases (
            release_key,
            status,
            dataset_fingerprint,
            taxonomy_version,
            scoring_version,
            combined_manifest,
            validated_at,
            activated_at
        )
        SELECT
            'legacy-v1',
            'active',
            repeat(
                md5(
                    COALESCE(
                        string_agg(slug || ':' || sha256, E'\n' ORDER BY slug),
                        'legacy-v1'
                    )
                ),
                2
            ),
            'v1.0.0',
            'v1.0.0',
            jsonb_build_object('migration', '0004', 'kind', 'legacy-backfill'),
            now(),
            now()
        FROM dataset_sources;

        CREATE TABLE data_release_sources (
            data_release_id bigint NOT NULL
                REFERENCES data_releases(id) ON DELETE CASCADE,
            dataset_source_id bigint NOT NULL
                REFERENCES dataset_sources(id) ON DELETE RESTRICT,
            role text NOT NULL,
            PRIMARY KEY (data_release_id, dataset_source_id, role),
            CONSTRAINT uq_data_release_sources_release_role
                UNIQUE (data_release_id, role)
        );
        CREATE INDEX ix_data_release_sources_dataset_source_id
            ON data_release_sources (dataset_source_id);

        INSERT INTO data_release_sources (data_release_id, dataset_source_id, role)
        SELECT release.id, source.id, source.slug
        FROM data_releases AS release
        CROSS JOIN dataset_sources AS source
        WHERE release.release_key = 'legacy-v1';

        ALTER TABLE dataset_sources DROP CONSTRAINT uq_dataset_sources_slug;
        ALTER TABLE dataset_sources
            ADD CONSTRAINT uq_dataset_sources_slug_sha256 UNIQUE (slug, sha256);

        ALTER TABLE business_categories
            DROP CONSTRAINT ck_business_categories_supported_slug;
        ALTER TABLE business_categories
            ADD CONSTRAINT ck_business_categories_supported_slug CHECK (
                slug IN (
                    'restaurant', 'gym', 'pharmacy', 'fnb', 'retail', 'services'
                )
            );
        INSERT INTO business_categories (
            slug, name, parent_category, description, is_active
        ) VALUES
            ('fnb', 'F&B', 'business', 'Food and beverage businesses', false),
            ('retail', 'Retail', 'business', 'Consumer retail businesses', false),
            ('services', 'Services', 'business', 'Consumer service businesses', false)
        ON CONFLICT (slug) DO NOTHING;

        ALTER TABLE businesses ADD COLUMN business_subtype text;
        ALTER TABLE businesses ADD COLUMN taxonomy_version text;
        UPDATE businesses
        SET
            business_subtype = category.slug,
            taxonomy_version = 'v1.0.0'
        FROM business_categories AS category
        WHERE category.id = businesses.category_id;
        ALTER TABLE businesses ALTER COLUMN business_subtype SET NOT NULL;
        ALTER TABLE businesses ALTER COLUMN taxonomy_version SET NOT NULL;
        """
    )

    for table_name in RELEASE_BOUND_TABLES:
        op.execute(f"ALTER TABLE {table_name} ADD COLUMN data_release_id bigint")
        op.execute(
            f"""
            UPDATE {table_name}
            SET data_release_id = (
                SELECT id FROM data_releases WHERE release_key = 'legacy-v1'
            )
            """
        )
        op.execute(
            f"ALTER TABLE {table_name} ALTER COLUMN data_release_id SET NOT NULL"
        )
        op.execute(
            f"""
            ALTER TABLE {table_name}
            ADD CONSTRAINT fk_{table_name}_data_release_id
            FOREIGN KEY (data_release_id) REFERENCES data_releases(id) ON DELETE CASCADE
            """
        )
        op.execute(
            f"CREATE INDEX ix_{table_name}_data_release_id ON {table_name} (data_release_id)"
        )

    op.execute(
        """
        ALTER TABLE administrative_areas
            DROP CONSTRAINT uq_administrative_areas_source_record;
        ALTER TABLE administrative_areas
            ADD CONSTRAINT uq_administrative_areas_source_record UNIQUE (
                data_release_id, dataset_source_id, source_record_id
            );

        ALTER TABLE businesses DROP CONSTRAINT uq_businesses_source_record;
        ALTER TABLE businesses
            ADD CONSTRAINT uq_businesses_source_record UNIQUE (
                data_release_id, dataset_source_id, source_type, source_record_id
            );

        ALTER TABLE pois DROP CONSTRAINT uq_pois_source_record;
        ALTER TABLE pois
            ADD CONSTRAINT uq_pois_source_record UNIQUE (
                data_release_id, dataset_source_id, source_type, source_record_id
            );

        ALTER TABLE transport_stops DROP CONSTRAINT uq_transport_stops_source_record;
        ALTER TABLE transport_stops
            ADD CONSTRAINT uq_transport_stops_source_record UNIQUE (
                data_release_id, dataset_source_id, source_record_id
            );

        ALTER TABLE roads DROP CONSTRAINT uq_roads_source_record;
        ALTER TABLE roads
            ADD CONSTRAINT uq_roads_source_record UNIQUE (
                data_release_id, dataset_source_id, source_type, source_record_id
            );

        ALTER TABLE normalization_profiles
            DROP CONSTRAINT uq_normalization_profiles_scope;
        ALTER TABLE normalization_profiles
            ADD CONSTRAINT uq_normalization_profiles_scope UNIQUE (
                data_release_id,
                category_id,
                radius_m,
                dataset_fingerprint,
                version
            );

        ALTER TABLE opportunity_scores DROP CONSTRAINT uq_opportunity_scores_scope;
        ALTER TABLE opportunity_scores
            ADD CONSTRAINT uq_opportunity_scores_scope UNIQUE (
                data_release_id,
                administrative_area_id,
                category_id,
                radius_m,
                dataset_fingerprint,
                scoring_version
            );

        DROP INDEX ix_opportunity_scores_lookup;
        CREATE INDEX ix_opportunity_scores_lookup
            ON opportunity_scores (
                data_release_id,
                category_id,
                radius_m,
                dataset_fingerprint,
                scoring_version,
                final_score DESC
            ) INCLUDE (administrative_area_id, label);

        CREATE INDEX ix_businesses_category_subtype_geom
            ON businesses USING gist (category_id, business_subtype, geom);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM data_releases WHERE release_key <> 'legacy-v1';
        DELETE FROM business_categories WHERE slug IN ('fnb', 'retail', 'services');

        DROP INDEX ix_businesses_category_subtype_geom;
        DROP INDEX ix_opportunity_scores_lookup;

        ALTER TABLE opportunity_scores DROP CONSTRAINT uq_opportunity_scores_scope;
        ALTER TABLE opportunity_scores
            ADD CONSTRAINT uq_opportunity_scores_scope UNIQUE (
                administrative_area_id,
                category_id,
                radius_m,
                dataset_fingerprint,
                scoring_version
            );
        CREATE INDEX ix_opportunity_scores_lookup
            ON opportunity_scores (
                category_id,
                radius_m,
                dataset_fingerprint,
                scoring_version,
                final_score DESC
            ) INCLUDE (administrative_area_id, label);

        ALTER TABLE normalization_profiles
            DROP CONSTRAINT uq_normalization_profiles_scope;
        ALTER TABLE normalization_profiles
            ADD CONSTRAINT uq_normalization_profiles_scope UNIQUE (
                category_id, radius_m, dataset_fingerprint, version
            );

        ALTER TABLE roads DROP CONSTRAINT uq_roads_source_record;
        ALTER TABLE roads ADD CONSTRAINT uq_roads_source_record
            UNIQUE (dataset_source_id, source_type, source_record_id);
        ALTER TABLE transport_stops DROP CONSTRAINT uq_transport_stops_source_record;
        ALTER TABLE transport_stops ADD CONSTRAINT uq_transport_stops_source_record
            UNIQUE (dataset_source_id, source_record_id);
        ALTER TABLE pois DROP CONSTRAINT uq_pois_source_record;
        ALTER TABLE pois ADD CONSTRAINT uq_pois_source_record
            UNIQUE (dataset_source_id, source_type, source_record_id);
        ALTER TABLE businesses DROP CONSTRAINT uq_businesses_source_record;
        ALTER TABLE businesses ADD CONSTRAINT uq_businesses_source_record
            UNIQUE (dataset_source_id, source_type, source_record_id);
        ALTER TABLE administrative_areas
            DROP CONSTRAINT uq_administrative_areas_source_record;
        ALTER TABLE administrative_areas
            ADD CONSTRAINT uq_administrative_areas_source_record
            UNIQUE (dataset_source_id, source_record_id);
        """
    )

    for table_name in reversed(RELEASE_BOUND_TABLES):
        op.execute(f"DROP INDEX ix_{table_name}_data_release_id")
        op.execute(
            f"ALTER TABLE {table_name} DROP CONSTRAINT fk_{table_name}_data_release_id"
        )
        op.execute(f"ALTER TABLE {table_name} DROP COLUMN data_release_id")

    op.execute(
        """
        ALTER TABLE businesses DROP COLUMN taxonomy_version;
        ALTER TABLE businesses DROP COLUMN business_subtype;

        ALTER TABLE business_categories
            DROP CONSTRAINT ck_business_categories_supported_slug;
        ALTER TABLE business_categories
            ADD CONSTRAINT ck_business_categories_supported_slug
            CHECK (slug IN ('restaurant', 'gym', 'pharmacy'));

        ALTER TABLE dataset_sources
            DROP CONSTRAINT uq_dataset_sources_slug_sha256;
        ALTER TABLE dataset_sources
            ADD CONSTRAINT uq_dataset_sources_slug UNIQUE (slug);

        DROP TABLE data_release_sources;
        DROP TABLE data_releases;
        """
    )
