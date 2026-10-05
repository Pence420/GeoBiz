from app.imports.staging import read_source_json


def test_read_source_json_accepts_utf8_bom(tmp_path) -> None:
    source = tmp_path / "boundary.geojson"
    source.write_bytes(b'\xef\xbb\xbf{"type":"FeatureCollection","features":[]}')

    assert read_source_json(source) == {
        "type": "FeatureCollection",
        "features": [],
    }
