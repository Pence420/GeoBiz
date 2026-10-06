import pytest

from app.imports.population import (
    KelurahanBoundary,
    PopulationRecord,
    join_population_to_boundaries,
    parse_population_records,
)


def test_aggregates_age_groups_into_one_population_per_kelurahan() -> None:
    payload = {
        "data": [
            {
                "periode_data": "2025",
                "wilayah": "JAKARTA PUSAT",
                "kecamatan": "GAMBIR",
                "kelurahan": "DURI PULO",
                "kelompok_umur": "00-04",
                "jumlah_penduduk": "100",
            },
            {
                "periode_data": "2025",
                "wilayah": "JAKARTA PUSAT",
                "kecamatan": "GAMBIR",
                "kelurahan": "DURI PULO",
                "kelompok_umur": "05-09",
                "jumlah_penduduk": "120",
            },
        ]
    }

    records = parse_population_records(payload, period="2025")

    assert records == [
        PopulationRecord(
            wilayah="JAKARTA PUSAT",
            kecamatan="GAMBIR",
            kelurahan="DURI PULO",
            population=220,
        )
    ]


def test_reviewed_alias_joins_population_without_silent_drop() -> None:
    populations = [
        PopulationRecord(
            wilayah="JAKARTA TIMUR",
            kecamatan="KRAMAT JATI",
            kelurahan="KRAMATJATI",
            population=10_000,
        )
    ]
    boundaries = [
        KelurahanBoundary(
            source_record_id="relation/1",
            name="Kramat Jati",
            properties={"name": "Kramat Jati"},
            geometry={
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
            },
        )
    ]

    joined, report = join_population_to_boundaries(
        populations, boundaries, aliases={"KRAMAT JATI": "KRAMATJATI"}
    )

    assert joined[0].population == 10_000
    assert report.join_rate == 1.0
    assert report.unmatched_population_names == []


def test_preserves_verified_age_and_gender_cohorts() -> None:
    payload = {"data": [
        {"periode_data": "2025", "wilayah": "JAKARTA PUSAT", "kecamatan": "GAMBIR",
         "kelurahan": "DURI PULO", "kelompok_umur": "00-04", "jumlah_laki_laki": "51",
         "jumlah_perempuan": "49", "jumlah_penduduk": "100"},
        {"periode_data": "2025", "wilayah": "JAKARTA PUSAT", "kecamatan": "GAMBIR",
         "kelurahan": "DURI PULO", "kelompok_umur": "05-09", "jumlah_laki_laki": "60",
         "jumlah_perempuan": "62", "jumlah_penduduk": "122"},
    ]}

    records = parse_population_records(payload, period="2025")

    assert records[0].population == 222
    assert records[0].age_gender == {
        "00-04": {"male": 51, "female": 49},
        "05-09": {"male": 60, "female": 62},
    }


def test_rejects_inconsistent_demographic_counts() -> None:
    payload = {"data": [{
        "periode_data": "2025", "wilayah": "JAKARTA PUSAT", "kecamatan": "GAMBIR",
        "kelurahan": "DURI PULO", "kelompok_umur": "00-04", "jumlah_laki_laki": "51",
        "jumlah_perempuan": "49", "jumlah_penduduk": "101",
    }]}

    with pytest.raises(ValueError, match="invalid age/gender total"):
        parse_population_records(payload, period="2025")
