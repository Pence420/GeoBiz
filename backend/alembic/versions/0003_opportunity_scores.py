"""Cache versioned opportunity scores for DKI kelurahan.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE opportunity_scores (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            administrative_area_id bigint NOT NULL
                REFERENCES administrative_areas(id) ON DELETE CASCADE,
            category_id bigint NOT NULL
                REFERENCES business_categories(id) ON DELETE CASCADE,
            radius_m bigint NOT NULL,
            dataset_fingerprint text NOT NULL,
            scoring_version text NOT NULL,
            final_score numeric(5,1) NOT NULL,
            label text NOT NULL,
            raw_factors jsonb NOT NULL,
            normalized_factors jsonb NOT NULL,
            representative_method text NOT NULL DEFAULT 'point_on_surface',
            generated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_opportunity_scores_scope UNIQUE (
                administrative_area_id,
                category_id,
                radius_m,
                dataset_fingerprint,
                scoring_version
            ),
            CONSTRAINT ck_opportunity_scores_radius
                CHECK (radius_m IN (500, 1000, 2000, 3000, 5000)),
            CONSTRAINT ck_opportunity_scores_range
                CHECK (final_score >= 0 AND final_score <= 100),
            CONSTRAINT ck_opportunity_scores_label
                CHECK (label IN ('Very Low', 'Low', 'Moderate', 'Good', 'High')),
            CONSTRAINT ck_opportunity_scores_representative_method
                CHECK (representative_method = 'point_on_surface')
        );

        CREATE INDEX ix_opportunity_scores_administrative_area_id
            ON opportunity_scores (administrative_area_id);
        CREATE INDEX ix_opportunity_scores_category_id
            ON opportunity_scores (category_id);
        CREATE INDEX ix_opportunity_scores_lookup
            ON opportunity_scores (
                category_id,
                radius_m,
                dataset_fingerprint,
                scoring_version,
                final_score DESC
            ) INCLUDE (administrative_area_id, label);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS opportunity_scores")
