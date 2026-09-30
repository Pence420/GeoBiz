from app.imports.osm_context import classify_poi_tags, parse_osm_context_geojson


def test_classifies_supported_context_tags_with_specific_precedence() -> None:
    assert classify_poi_tags({"shop": "supermarket"}) == "commercial"
    assert classify_poi_tags({"office": "company"}) == "office"
    assert classify_poi_tags({"amenity": "university"}) == "university"
    assert classify_poi_tags({"amenity": "hospital"}) == "hospital"
    assert classify_poi_tags({"shop": "chemist", "amenity": "clinic"}) == "clinic"


def test_parses_polygon_poi_and_linestring_road_with_source_identity() -> None:
    payload = {
        "features": [
            {
                "type": "Feature",
                "properties": {"@type": "way", "@id": 10, "shop": "mall"},
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [[[[106.8, -6.2], [106.81, -6.2], [106.8, -6.2]]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"@type": "way", "@id": 11, "highway": "primary"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[106.8, -6.2], [106.81, -6.21]],
                },
            },
        ]
    }

    pois, roads = parse_osm_context_geojson(payload)

    assert pois[0].source_type == "way"
    assert pois[0].source_record_id == "10"
    assert pois[0].poi_type == "commercial"
    assert pois[0].geometry["type"] == "MultiPolygon"
    assert roads[0].source_record_id == "11"
    assert roads[0].road_type == "primary"
