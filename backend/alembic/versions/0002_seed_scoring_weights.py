"""Seed the approved GeoBiz v1 scoring weights.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        WITH weight_data(category_slug, factor_name, weight, is_required) AS (
            VALUES
                ('restaurant', 'population_density', 0.20, true),
                ('restaurant', 'competition', 0.20, true),
                ('restaurant', 'public_transport', 0.15, true),
                ('restaurant', 'commercial_activity', 0.15, true),
                ('restaurant', 'office_activity', 0.20, true),
                ('restaurant', 'road_accessibility', 0.10, true),
                ('restaurant', 'healthcare_proximity', 0.00, false),
                ('gym', 'population_density', 0.30, true),
                ('gym', 'competition', 0.20, true),
                ('gym', 'public_transport', 0.10, true),
                ('gym', 'commercial_activity', 0.10, true),
                ('gym', 'office_activity', 0.15, true),
                ('gym', 'road_accessibility', 0.15, true),
                ('gym', 'healthcare_proximity', 0.00, false),
                ('pharmacy', 'population_density', 0.25, true),
                ('pharmacy', 'competition', 0.15, true),
                ('pharmacy', 'public_transport', 0.10, true),
                ('pharmacy', 'commercial_activity', 0.10, true),
                ('pharmacy', 'office_activity', 0.05, true),
                ('pharmacy', 'road_accessibility', 0.10, true),
                ('pharmacy', 'healthcare_proximity', 0.25, true)
        )
        INSERT INTO scoring_weights (
            category_id, version, factor_name, weight, is_required
        )
        SELECT category.id, 'v1.0.0', data.factor_name, data.weight, data.is_required
        FROM weight_data AS data
        JOIN business_categories AS category ON category.slug = data.category_slug;

        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM scoring_weights
                WHERE version = 'v1.0.0'
                GROUP BY category_id
                HAVING abs(sum(weight) - 1.0) > 0.0001
            ) THEN
                RAISE EXCEPTION 'GeoBiz v1 scoring weights must sum to 1.0';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM scoring_weights WHERE version = 'v1.0.0'")
