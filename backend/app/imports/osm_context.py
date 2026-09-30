from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field

from app.imports.administrative import point_in_geometry
from app.imports.osm import geometry_bbox_centre

ROAD_TYPES = frozenset(
    {
        "motorway",
        "motorway_link",
        "trunk",
        "trunk_link",
        "primary",
        "primary_link",
        "secondary",
        "secondary_link",
    }
)


class OsmPoiRecord(BaseModel):
    source_type: str
    source_record_id: str
    name: str | None
    poi_type: str
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    tags: dict[str, str]
    geometry: dict[str, Any]


class OsmRoadRecord(BaseModel):
    source_type: str
    source_record_id: str
    name: str | None
    road_type: str
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    tags: dict[str, str]
    geometry: dict[str, Any]


class OsmContextQualityReport(BaseModel):
    poi_candidates: int
    promoted_pois: int
    road_candidates: int
    promoted_roads: int
    outside_poi_count: int
    outside_road_count: int
    duplicate_source_id_count: int
    poi_type_counts: dict[str, int]


def classify_poi_tags(tags: Mapping[str, str]) -> str | None:
    amenity = tags.get("amenity")
    healthcare = tags.get("healthcare")
    if amenity == "hospital" or healthcare == "hospital":
        return "hospital"
    if amenity == "clinic" or healthcare == "clinic":
        return "clinic"
    if amenity == "doctors" or healthcare in {"doctor", "doctors"}:
        return "doctors"
    if amenity in {"university", "college", "school"}:
        return amenity
    if "office" in tags:
        return "office"
    if "shop" in tags or amenity in {"marketplace", "bank"}:
        return "commercial"
    return None


def parse_osm_context_geojson(
    payload: Mapping[str, Any],
) -> tuple[list[OsmPoiRecord], list[OsmRoadRecord]]:
    pois: list[OsmPoiRecord] = []
    roads: list[OsmRoadRecord] = []
    poi_seen: set[tuple[str, str]] = set()
    road_seen: set[tuple[str, str]] = set()
    features = payload.get("features", [])
    if not isinstance(features, list):
        return pois, roads

    for feature in features:
        if not isinstance(feature, Mapping):
            continue
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, Mapping) or not isinstance(geometry, Mapping):
            continue
        source_type = properties.get("@type")
        source_record_id = properties.get("@id")
        if source_type not in {"node", "way", "relation"} or not isinstance(
            source_record_id, (str, int)
        ):
            continue
        identity = (str(source_type), str(source_record_id))
        tags = {
            str(key): str(value)
            for key, value in properties.items()
            if not str(key).startswith("@")
            and isinstance(value, (str, int, float))
        }
        centre = geometry_bbox_centre(geometry)
        if centre is None:
            continue
        longitude, latitude = centre
        raw_name = tags.get("name")
        name = raw_name.strip() if raw_name and raw_name.strip() else None

        road_type = tags.get("highway")
        if road_type in ROAD_TYPES and geometry.get("type") in {
            "LineString",
            "MultiLineString",
        }:
            if identity not in road_seen:
                roads.append(
                    OsmRoadRecord(
                        source_type=identity[0],
                        source_record_id=identity[1],
                        name=name,
                        road_type=road_type,
                        longitude=longitude,
                        latitude=latitude,
                        tags=tags,
                        geometry=dict(geometry),
                    )
                )
                road_seen.add(identity)
            continue

        poi_type = classify_poi_tags(tags)
        if poi_type is None or geometry.get("type") not in {
            "Point",
            "Polygon",
            "MultiPolygon",
        }:
            continue
        if identity not in poi_seen:
            pois.append(
                OsmPoiRecord(
                    source_type=identity[0],
                    source_record_id=identity[1],
                    name=name,
                    poi_type=poi_type,
                    longitude=longitude,
                    latitude=latitude,
                    tags=tags,
                    geometry=dict(geometry),
                )
            )
            poi_seen.add(identity)
    return pois, roads


def filter_context_to_boundary(
    pois: Sequence[OsmPoiRecord],
    roads: Sequence[OsmRoadRecord],
    boundary: Mapping[str, Any],
) -> tuple[list[OsmPoiRecord], list[OsmRoadRecord], OsmContextQualityReport]:
    kept_pois = [
        record
        for record in pois
        if point_in_geometry(record.longitude, record.latitude, boundary)
    ]
    kept_roads = [
        record
        for record in roads
        if point_in_geometry(record.longitude, record.latitude, boundary)
    ]
    poi_counts: dict[str, int] = {}
    for record in kept_pois:
        poi_counts[record.poi_type] = poi_counts.get(record.poi_type, 0) + 1
    identities = [
        (record.source_type, record.source_record_id)
        for record in [*kept_pois, *kept_roads]
    ]
    duplicate_count = len(identities) - len(set(identities))
    return kept_pois, kept_roads, OsmContextQualityReport(
        poi_candidates=len(pois),
        promoted_pois=len(kept_pois),
        road_candidates=len(roads),
        promoted_roads=len(kept_roads),
        outside_poi_count=len(pois) - len(kept_pois),
        outside_road_count=len(roads) - len(kept_roads),
        duplicate_source_id_count=duplicate_count,
        poi_type_counts=poi_counts,
    )
