from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.analysis.contracts import AnalyzeLocationRequest
from app.analysis.service import build_analysis_service
from app.db.models import (
    BusinessCategory,
    DataRelease,
    DataReleaseSource,
    DatasetSource,
    NormalizationProfile,
)
from app.releases.service import activate_release, create_staging_release


def _activate_v2_release(session: Session) -> DataRelease:
    release = create_staging_release(
        session,
        {
            "release_key": "detailed-analysis-v2",
            "dataset_fingerprint": "d" * 64,
            "taxonomy_version": "v2.0.0",
            "scoring_version": "v2.0.0",
        },
    )
    release.status = "validated"
    session.flush()
    return activate_release(session, release.id)


def test_analysis_returns_traceable_nearest_evidence(db_session: Session) -> None:
    release = _activate_v2_release(db_session)
    source = DatasetSource(
        slug="detailed-analysis-osm",
        provider="OpenStreetMap",
        source_url="https://www.openstreetmap.org",
        license_name="ODbL-1.0",
        attribution="© OpenStreetMap contributors",
        observed_at=datetime(2026, 9, 29, tzinfo=UTC).date(),
        retrieved_at=datetime.now(UTC),
        sha256="e" * 64,
    )
    db_session.add(source)
    db_session.flush()
    db_session.add(
        DataReleaseSource(
            data_release_id=release.id,
            dataset_source_id=source.id,
            role="osm-dki",
        )
    )
    category_id = db_session.scalar(
        select(BusinessCategory.id).where(BusinessCategory.slug == "fnb")
    )
    assert category_id is not None

    seed_sql = """
            INSERT INTO administrative_areas (
                data_release_id, dataset_source_id, source_record_id,
                official_code, name, area_type, population, population_density,
                observed_at, retrieved_at, original_properties, geom
            ) VALUES
                (:release_id, :source_id, 'province', 'ID-JK', 'DKI JAKARTA',
                 'province', NULL, NULL, DATE '2025-12-31', now(), '{}'::jsonb,
                 ST_Multi(ST_MakeEnvelope(106.70, -6.35, 106.95, -6.05, 4326))),
                (:release_id, :source_id, 'kelurahan', NULL, 'SENAYAN',
                 'kelurahan', 25000, 17000, DATE '2025-12-31', now(),
                 '{"kecamatan":"KEBAYORAN BARU"}'::jsonb,
                 ST_Multi(ST_MakeEnvelope(106.79, -6.24, 106.82, -6.20, 4326)));

            INSERT INTO businesses (
                data_release_id, category_id, dataset_source_id, name,
                source_type, source_record_id, business_subtype,
                taxonomy_version, source_observed_at, retrieved_at,
                original_tags, geom
            ) VALUES
                (:release_id, :category_id, :source_id, 'Kopi Nyata',
                 'node', '101', 'cafe', 'v2.0.0', DATE '2026-09-29', now(),
                 '{"brand":"Kopi Nyata","opening_hours":"Mo-Su 08:00-22:00","addr:street":"Jalan Asia Afrika"}'::jsonb,
                 ST_SetSRID(ST_Point(106.8000, -6.2200), 4326)),
                (:release_id, :category_id, :source_id, 'Resto Nyata',
                 'node', '102', 'restaurant', 'v2.0.0', DATE '2026-09-29', now(),
                 '{}'::jsonb,
                 ST_SetSRID(ST_Point(106.8020, -6.2200), 4326));

            INSERT INTO transport_stops (
                data_release_id, dataset_source_id, name, transport_type,
                source_record_id, retrieved_at, original_properties, geom
            ) VALUES (
                :release_id, :source_id, 'Halte Senayan', 'bus', 'STOP-1',
                now(), '{}'::jsonb,
                ST_SetSRID(ST_Point(106.8030, -6.2200), 4326)
            );

            INSERT INTO roads (
                data_release_id, dataset_source_id, name, road_type,
                source_type, source_record_id, retrieved_at, original_tags, geom
            ) VALUES (
                :release_id, :source_id, 'Jalan Jenderal Sudirman', 'primary',
                'way', 'ROAD-1', now(), '{}'::jsonb,
                ST_Multi(ST_GeomFromText(
                    'LINESTRING(106.804 -6.23, 106.804 -6.21)', 4326
                ))
            );

            INSERT INTO pois (
                data_release_id, dataset_source_id, name, poi_type,
                source_type, source_record_id, retrieved_at, original_tags, geom
            ) VALUES
                (:release_id, :source_id, 'Mall Nyata', 'commercial', 'node',
                 'POI-1', now(), '{}'::jsonb,
                 ST_SetSRID(ST_Point(106.801, -6.221), 4326)),
                (:release_id, :source_id, 'Klinik Nyata', 'clinic', 'node',
                 'POI-2', now(), '{}'::jsonb,
                 ST_SetSRID(ST_Point(106.801, -6.222), 4326));
            """
    parameters = {
            "release_id": release.id,
            "source_id": source.id,
            "category_id": category_id,
        }
    for statement in seed_sql.strip().split(";\n\n"):
        db_session.execute(text(statement), parameters)
    db_session.add(
        NormalizationProfile(
            data_release_id=release.id,
            category_id=category_id,
            radius_m=1000,
            dataset_fingerprint=release.dataset_fingerprint,
            version="v2.0.0",
            percentiles={
                factor: [0, 1, 10, 100, 1000, 10000]
                for factor in (
                    "population_density",
                    "competition",
                    "public_transport",
                    "commercial_activity",
                    "office_activity",
                    "road_accessibility",
                )
            },
            sample_count=10,
        )
    )
    db_session.flush()

    response = build_analysis_service(db_session).analyze(
        AnalyzeLocationRequest(
            latitude=-6.22,
            longitude=106.80,
            business_category="fnb",
            radius_m=1000,
        )
    )

    assert response.taxonomy_version == "v2.0.0"
    assert response.scoring_version == "v2.0.0"
    assert response.competitor_subtype_counts == {"cafe": 1, "restaurant": 1}
    assert [item.source_record_id for item in response.nearest_competitors] == [
        "101",
        "102",
    ]
    assert response.nearest_competitors[0].brand == "Kopi Nyata"
    assert response.nearest_competitors[1].brand is None
    assert response.nearest_transport is not None
    assert response.nearest_transport.source_record_id == "STOP-1"
    assert response.nearest_major_road is not None
    assert response.nearest_major_road.source_record_id == "ROAD-1"
    assert response.poi_breakdown.commercial == {"commercial": 1}
    assert response.poi_breakdown.healthcare == {"clinic": 1}
    assert response.containing_area.kecamatan == "KEBAYORAN BARU"
    assert response.containing_area.population == 25000
    assert response.coverage.named_business_percent == 100
    assert response.source_snapshots[0].slug == "detailed-analysis-osm"
