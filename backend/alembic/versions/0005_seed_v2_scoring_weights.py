"""Seed the approved umbrella-category scoring weights.

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        WITH weight_data(category_slug, factor_name, weight, is_required) AS (
            VALUES
                ('fnb', 'population_density', 0.20, true),
                ('fnb', 'competition', 0.20, true),
                ('fnb', 'public_transport', 0.15, true),
                ('fnb', 'commercial_activity', 0.15, true),
                ('fnb', 'office_activity', 0.20, true),
                ('fnb', 'road_accessibility', 0.10, true),
                ('fnb', 'healthcare_proximity', 0.00, false),
                ('retail', 'population_density', 0.25, true),
                ('retail', 'competition', 0.20, true),
                ('retail', 'public_transport', 0.15, true),
                ('retail', 'commercial_activity', 0.20, true),
                ('retail', 'office_activity', 0.10, true),
                ('retail', 'road_accessibility', 0.10, true),
                ('retail', 'healthcare_proximity', 0.00, false),
                ('services', 'population_density', 0.25, true),
                ('services', 'competition', 0.20, true),
                ('services', 'public_transport', 0.10, true),
                ('services', 'commercial_activity', 0.15, true),
                ('services', 'office_activity', 0.15, true),
                ('services', 'road_accessibility', 0.15, true),
                ('services', 'healthcare_proximity', 0.00, false)
        )
        INSERT INTO scoring_weights (
            category_id, version, factor_name, weight, is_required
        )
        SELECT category.id, 'v2.0.0', data.factor_name, data.weight, data.is_required
        FROM weight_data AS data
        JOIN business_categories AS category ON category.slug = data.category_slug;

        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM scoring_weights AS scoring
                JOIN business_categories AS category
                  ON category.id = scoring.category_id
                WHERE scoring.version = 'v2.0.0'
                  AND category.slug IN ('fnb', 'retail', 'services')
                GROUP BY scoring.category_id
                HAVING abs(sum(scoring.weight) - 1.0) > 0.0001
            ) THEN
                RAISE EXCEPTION 'GeoBiz v2 scoring weights must sum to 1.0';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM scoring_weights WHERE version = 'v2.0.0'")
