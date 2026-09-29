import zipfile

from app.imports.gtfs import parse_gtfs_stops


def test_parses_parent_and_child_gtfs_stops_without_inventing_fields(tmp_path) -> None:
    archive_path = tmp_path / "feed.zip"
    stops = """stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station
PARENT,Central Station,-6.20,106.80,1,
PLATFORM,Central Platform,-6.201,106.801,0,PARENT
"""
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("stops.txt", stops)

    records = parse_gtfs_stops(archive_path)

    assert [record.source_record_id for record in records] == ["PARENT", "PLATFORM"]
    assert records[1].parent_source_record_id == "PARENT"
    assert records[0].transport_type == "station"
    assert records[1].transport_type == "bus_stop"
