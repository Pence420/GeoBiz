from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.datasets.service import active_release
from app.db.models import AdministrativeArea, DataReleaseSource, DatasetSource
from app.demographics.contracts import AgeGenderBand, DemographicArea, DemographicsResponse
from app.imports.manifest import load_verified_manifest
from app.imports.population import normalize_area_name, parse_population_records
from app.imports.staging import read_source_json


def _area_key(wilayah: str, kecamatan: str, kelurahan: str) -> tuple[str, str, str]:
    return tuple(normalize_area_name(value) for value in (wilayah, kecamatan, kelurahan))


@lru_cache(maxsize=8)
def _verified_snapshot(
    raw_path: str, manifest_path: str, expected_sha256: str
) -> dict[tuple[str, str, str], tuple[int, dict[str, dict[str, int]]]]:
    manifest = load_verified_manifest(Path(manifest_path), Path(raw_path))
    if manifest.sha256 != expected_sha256:
        raise ValueError("population source does not match the active release")
    if manifest.source_observed_at is None:
        raise ValueError("population period is missing from the verified manifest")
    records = parse_population_records(
        read_source_json(Path(raw_path)), period=str(manifest.source_observed_at.year)
    )
    return {
        _area_key(record.wilayah, record.kecamatan, record.kelurahan):
            (record.population, record.age_gender)
        for record in records
    }


def _fallback_snapshot(source: DatasetSource) -> dict[tuple[str, str, str], tuple[int, dict[str, dict[str, int]]]]:
    data_root = get_settings().tile_root.parent.parent
    manifest_path = data_root / "manifests" / f"{source.slug}.json"
    if not manifest_path.is_file():
        return {}
    raw_path = data_root / "raw" / "dki-population-2025.json"
    if not raw_path.is_file():
        return {}
    try:
        return _verified_snapshot(str(raw_path), str(manifest_path), source.sha256)
    except (OSError, ValueError):
        return {}


def _valid_cohorts(value: Any, population: int) -> dict[str, dict[str, int]]:
    if not isinstance(value, dict) or not value:
        return {}
    try:
        cohorts = {
            str(age): {"male": int(counts["male"]), "female": int(counts["female"])}
            for age, counts in value.items()
        }
    except (KeyError, TypeError, ValueError):
        return {}
    if any(count < 0 for values in cohorts.values() for count in values.values()):
        return {}
    if sum(values["male"] + values["female"] for values in cohorts.values()) != population:
        return {}
    return cohorts


def demographics(session: Session) -> DemographicsResponse:
    release = active_release(session)
    source = session.scalar(
        select(DatasetSource)
        .join(DataReleaseSource, DataReleaseSource.dataset_source_id == DatasetSource.id)
        .where(
            DataReleaseSource.data_release_id == release.id,
            DatasetSource.slug.like("satudata-dki-population%"),
        )
    )
    if source is None:
        raise LookupError("the active release has no population source")
    areas = session.scalars(
        select(AdministrativeArea)
        .where(
            AdministrativeArea.data_release_id == release.id,
            AdministrativeArea.area_type == "kelurahan",
            AdministrativeArea.population.is_not(None),
        )
        .order_by(AdministrativeArea.name)
    ).all()
    fallback = _fallback_snapshot(source) if any(
        not area.original_properties.get("age_gender") for area in areas
    ) else {}
    bands: dict[str, dict[str, int]] = defaultdict(lambda: {"male": 0, "female": 0})
    covered: list[DemographicArea] = []
    for area in areas:
        props = area.original_properties
        cohort = _valid_cohorts(props.get("age_gender"), int(area.population))
        if not cohort:
            population, raw_cohorts = fallback.get(
                _area_key(str(props.get("wilayah", "")), str(props.get("kecamatan", "")), area.name),
                (0, {}),
            )
            if population == area.population:
                cohort = _valid_cohorts(raw_cohorts, int(area.population))
        if not cohort:
            continue
        male = sum(values["male"] for values in cohort.values())
        female = sum(values["female"] for values in cohort.values())
        for age, counts in cohort.items():
            bands[age]["male"] += counts["male"]
            bands[age]["female"] += counts["female"]
        covered.append(DemographicArea(
            id=area.id,
            name=area.name,
            wilayah=str(props.get("wilayah", "")),
            kecamatan=str(props.get("kecamatan", "")),
            population=int(area.population),
            population_density=float(area.population_density) if area.population_density is not None else None,
            male=male,
            female=female,
        ))
    age_gender = [
        AgeGenderBand(age=age, male=counts["male"], female=counts["female"],
                      total=counts["male"] + counts["female"])
        for age, counts in sorted(bands.items(), key=lambda item: int(item[0].split("-")[0].replace("+", "")))
    ]
    return DemographicsResponse(
        release_id=release.id,
        release_key=release.release_key,
        dataset_fingerprint=release.dataset_fingerprint,
        source_name=source.slug,
        source_url=source.source_url,
        observed_at=source.observed_at,
        total_areas=len(areas),
        covered_areas=len(covered),
        total_population=sum(area.population for area in covered),
        male=sum(area.male for area in covered),
        female=sum(area.female for area in covered),
        age_gender=age_gender,
        areas=covered,
    )
