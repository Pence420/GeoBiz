import pytest

from app.imports.contracts import SourceIdentity
from app.imports.osm import (
    classify_osm_tags,
    is_exact_duplicate,
    parse_osmium_geojson,
    parse_overpass_businesses,
)


def test_maps_supported_real_business_tags() -> None:
    assert classify_osm_tags({"amenity": "restaurant"}) == "fnb"
    assert classify_osm_tags({"leisure": "fitness_centre"}) == "services"
    assert classify_osm_tags({"shop": "supermarket"}) == "retail"


def test_rejects_unrelated_or_ambiguous_tags() -> None:
    assert classify_osm_tags({"amenity": "pharmacy"}) is None
    assert classify_osm_tags({"leisure": "fitness_station"}) is None
    assert classify_osm_tags({"shop": "chemist"}) is None


def test_same_source_record_is_duplicate_but_nearby_branch_is_not() -> None:
    existing = SourceIdentity(provider="osm", source_type="node", source_record_id="123")

    assert is_exact_duplicate(
        existing,
        SourceIdentity(provider="osm", source_type="node", source_record_id="123"),
    )
    assert not is_exact_duplicate(
        existing,
        SourceIdentity(provider="osm", source_type="node", source_record_id="124"),
    )


def test_parses_nodes_and_way_centres_without_inventing_names() -> None:
    payload = {
        "osm3s": {"timestamp_osm_base": "2026-09-28T12:00:00Z"},
        "elements": [
            {
                "type": "node",
                "id": 10,
                "lat": -6.2,
                "lon": 106.8,
                "tags": {"amenity": "restaurant", "name": "Warung Nyata"},
            },
            {
                "type": "way",
                "id": 11,
                "center": {"lat": -6.21, "lon": 106.81},
                "tags": {"leisure": "fitness_centre"},
            },
            {
                "type": "node",
                "id": 12,
                "lat": -6.22,
                "lon": 106.82,
                "tags": {"amenity": "cafe", "name": "Not a Restaurant"},
            },
        ],
    }

    records = parse_overpass_businesses(payload)

    assert [
        (record.category_slug, record.business_subtype, record.name)
        for record in records
    ] == [
        ("fnb", "restaurant", "Warung Nyata"),
        ("services", "fitness_centre", None),
        ("fnb", "cafe", "Not a Restaurant"),
    ]
    assert records[1].identity.source_type == "way"
    assert records[1].longitude == 106.81
    assert all(record.taxonomy_version == "v2.0.0" for record in records)


def test_parses_osmium_geojson_points_and_polygon_centroids() -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "n123",
                "properties": {"amenity": "restaurant", "name": "Sate Asli"},
                "geometry": {"type": "Point", "coordinates": [106.82, -6.2]},
            },
            {
                "type": "Feature",
                "id": "w456",
                "properties": {"leisure": "fitness_centre"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [106.80, -6.22],
                        [106.82, -6.22],
                        [106.82, -6.20],
                        [106.80, -6.20],
                        [106.80, -6.22],
                    ]],
                },
            },
        ],
    }

    records = parse_osmium_geojson(payload)

    assert [(r.identity.source_type, r.identity.source_record_id) for r in records] == [
        ("node", "123"),
        ("way", "456"),
    ]
    assert records[1].name is None
    assert records[1].longitude == pytest.approx(106.81)
    assert records[1].latitude == pytest.approx(-6.21)
