from collections import Counter
from collections.abc import Sequence

from app.imports.contracts import ImportQualityReport
from app.imports.osm import OsmBusinessRecord


class ImportQualityError(ValueError):
    pass


def build_osm_quality_report(
    records: Sequence[OsmBusinessRecord],
    *,
    total_records: int,
    outside_coverage_count: int,
    exact_duplicate_count: int = 0,
    ambiguous_count: int = 0,
    unsupported_count: int = 0,
) -> ImportQualityReport:
    coordinate_groups = Counter(
        (record.category_slug, record.longitude, record.latitude) for record in records
    )
    duplicate_candidates = sum(count - 1 for count in coordinate_groups.values())
    return ImportQualityReport(
        total_records=total_records,
        promoted_records=len(records),
        invalid_geometry_count=0,
        missing_name_count=sum(record.name is None for record in records),
        exact_duplicate_count=exact_duplicate_count,
        duplicate_candidate_count=duplicate_candidates,
        outside_coverage_count=outside_coverage_count,
        administrative_join_rate=None,
        category_counts=dict(Counter(record.category_slug for record in records)),
        subtype_counts=dict(sorted(Counter(record.business_subtype for record in records).items())),
        ambiguous_count=ambiguous_count,
        unsupported_count=unsupported_count,
        failures=[],
    )


def assert_demo_quality(report: ImportQualityReport) -> None:
    if report.failures:
        raise ImportQualityError("quality report contains failures: " + "; ".join(report.failures))
    if report.invalid_geometry_count:
        raise ImportQualityError("invalid geometries must be resolved before promotion")
    if (
        report.administrative_join_rate is not None
        and report.administrative_join_rate < 0.95
    ):
        raise ImportQualityError("population join coverage must be at least 95%")

    required_categories = {"fnb", "retail", "services"}
    missing_categories = sorted(
        category
        for category in required_categories
        if report.category_counts.get(category, 0) == 0
    )
    if missing_categories:
        raise ImportQualityError(
            "every supported category must have non-zero real records; missing: "
            + ", ".join(missing_categories)
        )
