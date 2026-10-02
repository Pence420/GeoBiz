from app.imports.administrative import filter_records_to_boundary
from app.imports.contracts import SourceIdentity
from app.imports.osm import OsmBusinessRecord


def _record(record_id: str, longitude: float, latitude: float) -> OsmBusinessRecord:
    return OsmBusinessRecord(
        identity=SourceIdentity(
            provider="osm", source_type="node", source_record_id=record_id
        ),
        category_slug="fnb",
        business_subtype="restaurant",
        taxonomy_version="v2.0.0",
        name="Real source name",
        longitude=longitude,
        latitude=latitude,
        tags={"amenity": "restaurant"},
    )


def test_filters_records_to_polygon_and_excludes_holes() -> None:
    boundary = {
        "type": "Polygon",
        "coordinates": [
            [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
            [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]],
        ],
    }
    records = [
        _record("inside", 2, 2),
        _record("hole", 5, 5),
        _record("outside", 12, 2),
    ]

    kept, excluded = filter_records_to_boundary(records, boundary)

    assert [record.identity.source_record_id for record in kept] == ["inside"]
    assert excluded == 2
