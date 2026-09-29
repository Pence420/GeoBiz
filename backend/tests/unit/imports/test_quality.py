import pytest

from app.imports.contracts import ImportQualityReport, SourceIdentity
from app.imports.osm import OsmBusinessRecord
from app.imports.quality import (
    ImportQualityError,
    assert_demo_quality,
    build_osm_quality_report,
)


def valid_report(**overrides: object) -> ImportQualityReport:
    values: dict[str, object] = {
        "total_records": 100,
        "promoted_records": 100,
        "invalid_geometry_count": 0,
        "missing_name_count": 4,
        "exact_duplicate_count": 0,
        "duplicate_candidate_count": 2,
        "administrative_join_rate": 0.97,
        "category_counts": {"restaurant": 70, "gym": 10, "pharmacy": 20},
        "failures": [],
    }
    values.update(overrides)
    return ImportQualityReport.model_validate(values)


def test_accepts_report_with_real_coverage_and_reported_missing_names() -> None:
    assert_demo_quality(valid_report())


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"invalid_geometry_count": 1}, "invalid geometries"),
        ({"administrative_join_rate": 0.94}, "at least 95%"),
        ({"category_counts": {"restaurant": 1, "gym": 0, "pharmacy": 1}}, "non-zero"),
    ],
)
def test_rejects_unfit_demo_batches(override: dict[str, object], message: str) -> None:
    with pytest.raises(ImportQualityError, match=message):
        assert_demo_quality(valid_report(**override))


def test_build_report_counts_missing_names_and_duplicate_candidates() -> None:
    def record(record_id: str, category: str, name: str | None, longitude: float):
        return OsmBusinessRecord(
            identity=SourceIdentity(
                provider="osm", source_type="node", source_record_id=record_id
            ),
            category_slug=category,
            name=name,
            latitude=-6.2,
            longitude=longitude,
            tags={},
        )

    records = [
        record("1", "restaurant", "A", 106.8),
        record("2", "restaurant", None, 106.8),
        record("3", "gym", "B", 106.81),
        record("4", "pharmacy", "C", 106.82),
    ]

    report = build_osm_quality_report(
        records, total_records=7, outside_coverage_count=3
    )

    assert report.promoted_records == 4
    assert report.missing_name_count == 1
    assert report.duplicate_candidate_count == 1
    assert report.outside_coverage_count == 3
