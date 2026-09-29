from collections.abc import Mapping
import re
from typing import Any

from pydantic import BaseModel, Field

from app.imports.contracts import SourceIdentity

SUPPORTED_CATEGORY_TAGS: tuple[tuple[str, str, str], ...] = (
    ("amenity", "restaurant", "restaurant"),
    ("leisure", "fitness_centre", "gym"),
    ("amenity", "pharmacy", "pharmacy"),
    ("healthcare", "pharmacy", "pharmacy"),
)


class OsmBusinessRecord(BaseModel):
    identity: SourceIdentity
    category_slug: str
    name: str | None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    tags: dict[str, str]


def classify_osm_tags(tags: Mapping[str, str]) -> str | None:
    matches = {
        category
        for key, value, category in SUPPORTED_CATEGORY_TAGS
        if tags.get(key) == value
    }
    if len(matches) != 1:
        return None
    return matches.pop()


def is_exact_duplicate(left: SourceIdentity, right: SourceIdentity) -> bool:
    return left == right


def parse_overpass_businesses(payload: Mapping[str, Any]) -> list[OsmBusinessRecord]:
    records: list[OsmBusinessRecord] = []
    seen: set[SourceIdentity] = set()

    for element in payload.get("elements", []):
        if not isinstance(element, Mapping):
            continue
        tags = element.get("tags")
        if not isinstance(tags, Mapping):
            continue
        string_tags = {
            str(key): str(value)
            for key, value in tags.items()
            if isinstance(key, str) and isinstance(value, (str, int, float))
        }
        category_slug = classify_osm_tags(string_tags)
        if category_slug is None:
            continue

        source_type = str(element.get("type", ""))
        source_record_id = str(element.get("id", ""))
        if source_type not in {"node", "way", "relation"} or not source_record_id:
            continue

        coordinate_source = element if source_type == "node" else element.get("center", {})
        if not isinstance(coordinate_source, Mapping):
            continue
        latitude = coordinate_source.get("lat")
        longitude = coordinate_source.get("lon")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            continue

        identity = SourceIdentity(
            provider="osm",
            source_type=source_type,
            source_record_id=source_record_id,
        )
        if identity in seen:
            continue
        seen.add(identity)
        raw_name = string_tags.get("name")
        name = raw_name.strip() if raw_name and raw_name.strip() else None
        records.append(
            OsmBusinessRecord(
                identity=identity,
                category_slug=category_slug,
                name=name,
                latitude=float(latitude),
                longitude=float(longitude),
                tags=string_tags,
            )
        )

    return records


def parse_osmium_geojson(payload: Mapping[str, Any]) -> list[OsmBusinessRecord]:
    records: list[OsmBusinessRecord] = []
    seen: set[SourceIdentity] = set()
    features = payload.get("features", [])
    if not isinstance(features, list):
        return records

    for feature in features:
        if not isinstance(feature, Mapping):
            continue
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, Mapping) or not isinstance(geometry, Mapping):
            continue
        if geometry.get("type") not in {"Point", "Polygon", "MultiPolygon"}:
            continue

        tags = {
            str(key): str(value)
            for key, value in properties.items()
            if not str(key).startswith("@")
            and isinstance(value, (str, int, float))
        }
        category_slug = classify_osm_tags(tags)
        if category_slug is None:
            continue

        parsed_identity = _parse_osm_feature_identity(feature, properties)
        if parsed_identity is None or parsed_identity in seen:
            continue

        centre = _geometry_bbox_centre(geometry)
        if centre is None:
            continue
        longitude, latitude = centre
        raw_name = tags.get("name")
        name = raw_name.strip() if raw_name and raw_name.strip() else None
        records.append(
            OsmBusinessRecord(
                identity=parsed_identity,
                category_slug=category_slug,
                name=name,
                latitude=latitude,
                longitude=longitude,
                tags=tags,
            )
        )
        seen.add(parsed_identity)

    return records


def _parse_osm_feature_identity(
    feature: Mapping[str, Any], properties: Mapping[str, Any]
) -> SourceIdentity | None:
    source_type = properties.get("@type")
    source_record_id = properties.get("@id")
    if source_type in {"node", "way", "relation"} and isinstance(
        source_record_id, (str, int)
    ):
        return SourceIdentity(
            provider="osm",
            source_type=str(source_type),
            source_record_id=str(source_record_id),
        )

    value = feature.get("id")
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"(?:(node|way|relation)/|([nwr]))(\d+)", value)
    if match is None:
        return None
    source_type = match.group(1) or {"n": "node", "w": "way", "r": "relation"}[
        match.group(2)
    ]
    return SourceIdentity(
        provider="osm",
        source_type=source_type,
        source_record_id=match.group(3),
    )


def _geometry_bbox_centre(geometry: Mapping[str, Any]) -> tuple[float, float] | None:
    coordinates = geometry.get("coordinates")
    values: list[tuple[float, float]] = []

    def collect(value: object) -> None:
        if (
            isinstance(value, (list, tuple))
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            values.append((float(value[0]), float(value[1])))
            return
        if isinstance(value, (list, tuple)):
            for child in value:
                collect(child)

    collect(coordinates)
    if not values:
        return None
    longitudes, latitudes = zip(*values, strict=True)
    return (
        (min(longitudes) + max(longitudes)) / 2,
        (min(latitudes) + max(latitudes)) / 2,
    )
