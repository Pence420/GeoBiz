"""Create the initial GeoBiz spatial schema.

Revision ID: 0001
Revises: None
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        CREATE TABLE business_categories (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            slug text NOT NULL,
            name text NOT NULL,
            parent_category text NOT NULL,
            description text,
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_business_categories_slug UNIQUE (slug),
            CONSTRAINT ck_business_categories_supported_slug
                CHECK (slug IN ('restaurant', 'gym', 'pharmacy'))
        );

        CREATE TABLE dataset_sources (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            slug text NOT NULL,
            provider text NOT NULL,
            source_url text NOT NULL,
            license_name text NOT NULL,
            attribution text NOT NULL,
            observed_at date,
            retrieved_at timestamptz NOT NULL,
            sha256 text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_dataset_sources_slug UNIQUE (slug)
        );

        CREATE TABLE import_runs (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            dataset_source_id bigint NOT NULL REFERENCES dataset_sources(id) ON DELETE RESTRICT,
            status text NOT NULL,
            manifest jsonb NOT NULL,
            quality_report jsonb,
            completed_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_import_runs_status
                CHECK (status IN ('staged', 'validated', 'promoted', 'rejected'))
        );
        CREATE INDEX ix_import_runs_dataset_source_id ON import_runs (dataset_source_id);

        CREATE TABLE administrative_areas (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            dataset_source_id bigint NOT NULL REFERENCES dataset_sources(id) ON DELETE RESTRICT,
            source_record_id text NOT NULL,
            official_code text,
            name text NOT NULL,
            area_type text NOT NULL,
            population bigint,
            population_density numeric(14,4),
            observed_at date,
            retrieved_at timestamptz NOT NULL,
            original_properties jsonb NOT NULL,
            geom geometry(MULTIPOLYGON, 4326) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_administrative_areas_source_record
                UNIQUE (dataset_source_id, source_record_id),
            CONSTRAINT ck_administrative_areas_population
                CHECK (population IS NULL OR population >= 0),
            CONSTRAINT ck_administrative_areas_population_density
                CHECK (population_density IS NULL OR population_density >= 0)
        );
        CREATE INDEX ix_administrative_areas_dataset_source_id
            ON administrative_areas (dataset_source_id);
        CREATE INDEX ix_administrative_areas_official_code
            ON administrative_areas (official_code);
        CREATE INDEX ix_administrative_areas_geom_gist
            ON administrative_areas USING gist (geom);

        CREATE TABLE businesses (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            category_id bigint NOT NULL REFERENCES business_categories(id) ON DELETE RESTRICT,
            dataset_source_id bigint NOT NULL REFERENCES dataset_sources(id) ON DELETE RESTRICT,
            name text,
            source_type text NOT NULL,
            source_record_id text NOT NULL,
            source_observed_at date,
            retrieved_at timestamptz NOT NULL,
            original_tags jsonb NOT NULL,
            geom geometry(POINT, 4326) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_businesses_source_record
                UNIQUE (dataset_source_id, source_type, source_record_id)
        );
        CREATE INDEX ix_businesses_category_id ON businesses (category_id);
        CREATE INDEX ix_businesses_dataset_source_id ON businesses (dataset_source_id);
        CREATE INDEX ix_businesses_category_geom
            ON businesses USING gist (category_id, geom);
        CREATE INDEX ix_businesses_geom_gist ON businesses USING gist (geom);

        CREATE TABLE pois (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            dataset_source_id bigint NOT NULL REFERENCES dataset_sources(id) ON DELETE RESTRICT,
            name text,
            poi_type text NOT NULL,
            source_type text NOT NULL,
            source_record_id text NOT NULL,
            retrieved_at timestamptz NOT NULL,
            original_tags jsonb NOT NULL,
            geom geometry(GEOMETRY, 4326) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_pois_source_record
                UNIQUE (dataset_source_id, source_type, source_record_id)
        );
        CREATE INDEX ix_pois_dataset_source_id ON pois (dataset_source_id);
        CREATE INDEX ix_pois_type_geom ON pois USING gist (poi_type, geom);
        CREATE INDEX ix_pois_geom_gist ON pois USING gist (geom);

        CREATE TABLE transport_stops (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            dataset_source_id bigint NOT NULL REFERENCES dataset_sources(id) ON DELETE RESTRICT,
            name text NOT NULL,
            transport_type text NOT NULL,
            source_record_id text NOT NULL,
            parent_stop_id bigint REFERENCES transport_stops(id) ON DELETE SET NULL,
            retrieved_at timestamptz NOT NULL,
            original_properties jsonb NOT NULL,
            geom geometry(POINT, 4326) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_transport_stops_source_record
                UNIQUE (dataset_source_id, source_record_id)
        );
        CREATE INDEX ix_transport_stops_dataset_source_id ON transport_stops (dataset_source_id);
        CREATE INDEX ix_transport_stops_parent_stop_id ON transport_stops (parent_stop_id);
        CREATE INDEX ix_transport_stops_geom_gist ON transport_stops USING gist (geom);

        CREATE TABLE roads (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            dataset_source_id bigint NOT NULL REFERENCES dataset_sources(id) ON DELETE RESTRICT,
            name text,
            road_type text NOT NULL,
            source_type text NOT NULL,
            source_record_id text NOT NULL,
            retrieved_at timestamptz NOT NULL,
            original_tags jsonb NOT NULL,
            geom geometry(MULTILINESTRING, 4326) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_roads_source_record
                UNIQUE (dataset_source_id, source_type, source_record_id)
        );
        CREATE INDEX ix_roads_dataset_source_id ON roads (dataset_source_id);
        CREATE INDEX ix_roads_type_geom ON roads USING gist (road_type, geom);
        CREATE INDEX ix_roads_geom_gist ON roads USING gist (geom);

        CREATE TABLE scoring_weights (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            category_id bigint NOT NULL REFERENCES business_categories(id) ON DELETE CASCADE,
            version text NOT NULL,
            factor_name text NOT NULL,
            weight numeric(5,4) NOT NULL,
            is_required boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_scoring_weights_category_version_factor
                UNIQUE (category_id, version, factor_name),
            CONSTRAINT ck_scoring_weights_range CHECK (weight >= 0 AND weight <= 1)
        );
        CREATE INDEX ix_scoring_weights_category_id ON scoring_weights (category_id);

        CREATE TABLE normalization_profiles (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            category_id bigint NOT NULL REFERENCES business_categories(id) ON DELETE CASCADE,
            radius_m bigint NOT NULL,
            dataset_fingerprint text NOT NULL,
            version text NOT NULL,
            percentiles jsonb NOT NULL,
            sample_count bigint NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_normalization_profiles_scope
                UNIQUE (category_id, radius_m, dataset_fingerprint, version),
            CONSTRAINT ck_normalization_profiles_radius
                CHECK (radius_m IN (500, 1000, 2000, 3000, 5000)),
            CONSTRAINT ck_normalization_profiles_sample_count CHECK (sample_count > 0)
        );
        CREATE INDEX ix_normalization_profiles_category_id
            ON normalization_profiles (category_id);

        INSERT INTO business_categories (slug, name, parent_category, description)
        VALUES
            ('restaurant', 'Restaurant', 'food_and_beverage', 'Food-service restaurant locations'),
            ('gym', 'Gym', 'services', 'Fitness centres and gyms'),
            ('pharmacy', 'Pharmacy', 'healthcare', 'Retail pharmacy locations');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS normalization_profiles;
        DROP TABLE IF EXISTS scoring_weights;
        DROP TABLE IF EXISTS roads;
        DROP TABLE IF EXISTS transport_stops;
        DROP TABLE IF EXISTS pois;
        DROP TABLE IF EXISTS businesses;
        DROP TABLE IF EXISTS administrative_areas;
        DROP TABLE IF EXISTS import_runs;
        DROP TABLE IF EXISTS dataset_sources;
        DROP TABLE IF EXISTS business_categories;
        """
    )
