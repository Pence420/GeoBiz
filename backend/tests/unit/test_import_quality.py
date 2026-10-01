from app.imports.contracts import SourceIdentity
from app.imports.osm import OsmBusinessRecord
from app.imports.quality import build_osm_quality_report


def test_quality_report_includes_subtypes_and_classification_rejections() -> None:
    records = [
        OsmBusinessRecord(
            identity=SourceIdentity(
                provider="osm", source_type="node", source_record_id="1"
            ),
            category_slug="fnb",
            business_subtype="restaurant",
            taxonomy_version="v2.0.0",
            name="Warung Nyata",
            latitude=-6.2,
            longitude=106.8,
            tags={"amenity": "restaurant"},
        ),
        OsmBusinessRecord(
            identity=SourceIdentity(
                provider="osm", source_type="node", source_record_id="2"
            ),
            category_slug="fnb",
            business_subtype="cafe",
            taxonomy_version="v2.0.0",
            name=None,
            latitude=-6.21,
            longitude=106.81,
            tags={"amenity": "cafe"},
        ),
    ]

    report = build_osm_quality_report(
        records,
        total_records=7,
        outside_coverage_count=1,
        ambiguous_count=2,
        unsupported_count=2,
    )

    assert report.category_counts == {"fnb": 2}
    assert report.subtype_counts == {"cafe": 1, "restaurant": 1}
    assert report.ambiguous_count == 2
    assert report.unsupported_count == 2
    assert report.missing_name_count == 1
