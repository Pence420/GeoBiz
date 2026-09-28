from collections.abc import Mapping
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
