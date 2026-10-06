import hashlib
import json

import pytest

from app.demographics.service import _area_key, _valid_cohorts, _verified_snapshot


def test_demographic_area_key_uses_reviewed_geography_names() -> None:
    assert _area_key("JAKARTA PUSAT", "GAMBIR", "Duri Pulo") == (
        "JAKARTA PUSAT", "GAMBIR", "DURI PULO"
    )


def test_only_complete_cohorts_are_exposed() -> None:
    valid = {"00-04": {"male": 51, "female": 49}}

    assert _valid_cohorts(valid, 100) == valid
    assert _valid_cohorts(valid, 101) == {}
    assert _valid_cohorts({"00-04": {"male": -1, "female": 101}}, 100) == {}


def test_existing_release_fallback_requires_matching_verified_snapshot(tmp_path) -> None:
    raw = tmp_path / "dki-population-2025.json"
    raw.write_text(json.dumps({"data": [{
        "periode_data": "2025", "wilayah": "JAKARTA PUSAT", "kecamatan": "GAMBIR",
        "kelurahan": "DURI PULO", "kelompok_umur": "00-04",
        "jumlah_laki_laki": "51", "jumlah_perempuan": "49", "jumlah_penduduk": "100",
    }]}), encoding="utf-8")
    checksum = hashlib.sha256(raw.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "dataset_slug": "satudata-dki-population-2025",
        "source_name": "Population 2025",
        "source_url": "https://satudata.jakarta.go.id/example",
        "source_license": "Satu Data Jakarta public open data",
        "source_observed_at": "2025-12-31",
        "retrieved_at": "2026-09-29T16:02:00Z",
        "sha256": checksum,
        "local_filename": raw.name,
    }), encoding="utf-8")

    records = _verified_snapshot(str(raw), str(manifest), checksum)
    assert records[("JAKARTA PUSAT", "GAMBIR", "DURI PULO")] == (
        100, {"00-04": {"male": 51, "female": 49}}
    )
    with pytest.raises(ValueError, match="does not match the active release"):
        _verified_snapshot(str(raw), str(manifest), "0" * 64)
