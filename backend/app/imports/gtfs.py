import csv
import io
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.imports.administrative import point_in_geometry


class GtfsStopRecord(BaseModel):
    source_record_id: str
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    transport_type: str
    parent_source_record_id: str | None
    properties: dict[str, str]


class GtfsQualityReport(BaseModel):
    total_records: int
    promoted_records: int
    outside_coverage_count: int
    missing_parent_count: int
    duplicate_source_id_count: int


def parse_gtfs_stops(archive_path: Path) -> list[GtfsStopRecord]:
    with zipfile.ZipFile(archive_path) as archive:
        content = archive.read("stops.txt").decode("utf-8-sig")
    records: list[GtfsStopRecord] = []
    for row in csv.DictReader(io.StringIO(content)):
        stop_id = (row.get("stop_id") or "").strip()
        name = (row.get("stop_name") or "").strip()
        try:
            latitude = float(row.get("stop_lat") or "")
            longitude = float(row.get("stop_lon") or "")
        except ValueError:
            continue
        if not stop_id or not name:
            continue
        location_type = (row.get("location_type") or "0").strip()
        parent = (row.get("parent_station") or "").strip() or None
        records.append(
            GtfsStopRecord(
                source_record_id=stop_id,
                name=name,
                latitude=latitude,
                longitude=longitude,
                transport_type="station" if location_type == "1" else "bus_stop",
                parent_source_record_id=parent,
                properties={key: value for key, value in row.items() if value is not None},
            )
        )
    return records


def filter_gtfs_to_boundary(
    records: Sequence[GtfsStopRecord], geometry: Mapping[str, Any]
) -> tuple[list[GtfsStopRecord], GtfsQualityReport]:
    kept = [
        record
        for record in records
        if point_in_geometry(record.longitude, record.latitude, geometry)
    ]
    counts: dict[str, int] = {}
    for record in kept:
        counts[record.source_record_id] = counts.get(record.source_record_id, 0) + 1
    duplicates = sum(count - 1 for count in counts.values())
    kept_ids = set(counts)
    missing_parents = sum(
        record.parent_source_record_id is not None
        and record.parent_source_record_id not in kept_ids
        for record in kept
    )
    return kept, GtfsQualityReport(
        total_records=len(records),
        promoted_records=len(kept),
        outside_coverage_count=len(records) - len(kept),
        missing_parent_count=missing_parents,
        duplicate_source_id_count=duplicates,
    )
