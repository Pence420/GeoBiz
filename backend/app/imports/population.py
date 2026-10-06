import csv
import re
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.imports.administrative import point_in_geometry
from app.imports.osm import geometry_bbox_centre


class PopulationRecord(BaseModel):
    wilayah: str
    kecamatan: str
    kelurahan: str
    population: int = Field(ge=0)
    age_gender: dict[str, dict[str, int]] = Field(default_factory=dict)


class KelurahanBoundary(BaseModel):
    source_record_id: str
    name: str
    properties: dict[str, Any]
    geometry: dict[str, Any]


class JoinedKelurahan(BaseModel):
    source_record_id: str
    name: str
    wilayah: str
    kecamatan: str
    population: int
    age_gender: dict[str, dict[str, int]] = Field(default_factory=dict)
    properties: dict[str, Any]
    geometry: dict[str, Any]


class PopulationQualityReport(BaseModel):
    source_rows: int
    population_areas: int
    boundary_candidates: int
    joined_areas: int
    join_rate: float = Field(ge=0, le=1)
    unmatched_population_names: list[str]
    unmatched_boundary_names: list[str]


def normalize_area_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).upper()
    return re.sub(r"[^A-Z0-9]+", " ", normalized).strip()


def parse_population_records(
    payload: Mapping[str, Any], *, period: str
) -> list[PopulationRecord]:
    aggregates: dict[tuple[str, str, str], int] = {}
    age_gender: dict[tuple[str, str, str], dict[str, dict[str, int]]] = {}
    rows = payload.get("data", [])
    if not isinstance(rows, list):
        return []
    for row in rows:
        if not isinstance(row, Mapping) or str(row.get("periode_data")) != period:
            continue
        wilayah = str(row.get("wilayah", "")).strip()
        kecamatan = str(row.get("kecamatan", "")).strip()
        kelurahan = str(row.get("kelurahan", "")).strip()
        if not all((wilayah, kecamatan, kelurahan)):
            continue
        try:
            population = int(str(row.get("jumlah_penduduk", "0")).replace(".", ""))
        except ValueError:
            continue
        key = (wilayah, kecamatan, kelurahan)
        aggregates[key] = aggregates.get(key, 0) + population
        age = str(row.get("kelompok_umur", "")).strip()
        male_raw = row.get("jumlah_laki_laki")
        female_raw = row.get("jumlah_perempuan")
        if age and male_raw is not None and female_raw is not None:
            male = int(str(male_raw).replace(".", ""))
            female = int(str(female_raw).replace(".", ""))
            if male < 0 or female < 0 or male + female != population:
                raise ValueError(f"invalid age/gender total for {key} {age}")
            cohorts = age_gender.setdefault(key, {})
            if age in cohorts:
                raise ValueError(f"duplicate age cohort for {key} {age}")
            cohorts[age] = {"male": male, "female": female}
        elif male_raw is not None or female_raw is not None:
            raise ValueError(f"incomplete age/gender data for {key}")
    for key, cohorts in age_gender.items():
        cohort_total = sum(values["male"] + values["female"] for values in cohorts.values())
        if cohort_total != aggregates[key]:
            raise ValueError(f"age/gender cohorts do not match population for {key}")
    if age_gender and (
        len(age_gender) != len(aggregates)
        or len({tuple(sorted(cohorts)) for cohorts in age_gender.values()}) != 1
    ):
        raise ValueError("age/gender cohorts are incomplete across kelurahan")
    return [
        PopulationRecord(
            wilayah=wilayah,
            kecamatan=kecamatan,
            kelurahan=kelurahan,
            population=population,
            age_gender=age_gender.get((wilayah, kecamatan, kelurahan), {}),
        )
        for (wilayah, kecamatan, kelurahan), population in sorted(aggregates.items())
    ]


def parse_kelurahan_boundaries(
    payload: Mapping[str, Any], province_boundary: Mapping[str, Any]
) -> list[KelurahanBoundary]:
    records: list[KelurahanBoundary] = []
    for feature in payload.get("features", []):
        if not isinstance(feature, Mapping):
            continue
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, Mapping) or not isinstance(geometry, Mapping):
            continue
        if properties.get("admin_level") != "7":
            continue
        centre = geometry_bbox_centre(geometry)
        if centre is None or not point_in_geometry(
            centre[0], centre[1], province_boundary
        ):
            continue
        name = str(properties.get("name", "")).strip()
        source_type = properties.get("@type")
        source_id = properties.get("@id")
        if not name or source_type not in {"way", "relation"} or not isinstance(
            source_id, (str, int)
        ):
            continue
        records.append(
            KelurahanBoundary(
                source_record_id=f"{source_type}/{source_id}",
                name=name,
                properties=dict(properties),
                geometry=dict(geometry),
            )
        )
    return records


def load_population_aliases(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {
            normalize_area_name(row["source_name"]): normalize_area_name(
                row["official_name"]
            )
            for row in csv.DictReader(handle)
            if row.get("source_name") and row.get("official_name")
        }


def join_population_to_boundaries(
    populations: Sequence[PopulationRecord],
    boundaries: Sequence[KelurahanBoundary],
    *,
    aliases: Mapping[str, str],
    source_rows: int = 0,
) -> tuple[list[JoinedKelurahan], PopulationQualityReport]:
    population_by_name = {
        normalize_area_name(record.kelurahan): record for record in populations
    }
    joined: list[JoinedKelurahan] = []
    matched_names: set[str] = set()
    unmatched_boundaries: list[str] = []
    for boundary in boundaries:
        source_name = normalize_area_name(boundary.name)
        target_name = aliases.get(source_name, source_name)
        population = population_by_name.get(target_name)
        if population is None:
            unmatched_boundaries.append(boundary.name)
            continue
        matched_names.add(target_name)
        joined.append(
            JoinedKelurahan(
                source_record_id=boundary.source_record_id,
                name=population.kelurahan,
                wilayah=population.wilayah,
                kecamatan=population.kecamatan,
                population=population.population,
                age_gender=population.age_gender,
                properties=boundary.properties,
                geometry=boundary.geometry,
            )
        )
    unmatched_population = sorted(
        record.kelurahan
        for key, record in population_by_name.items()
        if key not in matched_names
    )
    denominator = len(population_by_name)
    report = PopulationQualityReport(
        source_rows=source_rows,
        population_areas=denominator,
        boundary_candidates=len(boundaries),
        joined_areas=len(joined),
        join_rate=len(matched_names) / denominator if denominator else 0,
        unmatched_population_names=unmatched_population,
        unmatched_boundary_names=sorted(unmatched_boundaries),
    )
    return joined, report
