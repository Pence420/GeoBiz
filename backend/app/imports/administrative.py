from collections.abc import Mapping, Sequence
from typing import Any

from app.imports.osm import OsmBusinessRecord


def boundary_geometry(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if payload.get("type") == "FeatureCollection":
        features = payload.get("features")
        if not isinstance(features, list) or len(features) != 1:
            raise ValueError("boundary must contain exactly one feature")
        geometry = features[0].get("geometry")
    elif payload.get("type") == "Feature":
        geometry = payload.get("geometry")
    else:
        geometry = payload
    if not isinstance(geometry, Mapping) or geometry.get("type") not in {
        "Polygon",
        "MultiPolygon",
    }:
        raise ValueError("boundary geometry must be Polygon or MultiPolygon")
    return geometry


def filter_records_to_boundary(
    records: Sequence[OsmBusinessRecord], boundary: Mapping[str, Any]
) -> tuple[list[OsmBusinessRecord], int]:
    kept = [
        record
        for record in records
        if point_in_geometry(record.longitude, record.latitude, boundary)
    ]
    return kept, len(records) - len(kept)


def point_in_geometry(longitude: float, latitude: float, geometry: Mapping[str, Any]) -> bool:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon" and isinstance(coordinates, list):
        return _point_in_polygon(longitude, latitude, coordinates)
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        return any(
            _point_in_polygon(longitude, latitude, polygon)
            for polygon in coordinates
            if isinstance(polygon, list)
        )
    return False


def _point_in_polygon(longitude: float, latitude: float, rings: list[Any]) -> bool:
    if not rings or not _point_in_ring(longitude, latitude, rings[0]):
        return False
    return not any(
        _point_in_ring(longitude, latitude, ring)
        for ring in rings[1:]
        if isinstance(ring, list)
    )


def _point_in_ring(longitude: float, latitude: float, ring: object) -> bool:
    if not isinstance(ring, list) or len(ring) < 4:
        return False
    inside = False
    previous = ring[-1]
    for current in ring:
        if not (_coordinate(previous) and _coordinate(current)):
            previous = current
            continue
        x1, y1 = float(previous[0]), float(previous[1])
        x2, y2 = float(current[0]), float(current[1])
        crosses = (y1 > latitude) != (y2 > latitude)
        if crosses:
            intersection = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < intersection:
                inside = not inside
        previous = current
    return inside


def _coordinate(value: object) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    )
