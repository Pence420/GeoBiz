from app.imports.contracts import ImportQualityReport


class ImportQualityError(ValueError):
    pass


def assert_demo_quality(report: ImportQualityReport) -> None:
    if report.invalid_geometry_count:
        raise ImportQualityError("invalid geometries must be resolved before promotion")
    if (
        report.administrative_join_rate is not None
        and report.administrative_join_rate < 0.95
    ):
        raise ImportQualityError("population join coverage must be at least 95%")

    required_categories = {"restaurant", "gym", "pharmacy"}
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
