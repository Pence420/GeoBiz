from datetime import date

from pydantic import BaseModel


class AgeGenderBand(BaseModel):
    age: str
    male: int
    female: int
    total: int


class DemographicArea(BaseModel):
    id: int
    name: str
    wilayah: str
    kecamatan: str
    population: int
    population_density: float | None
    male: int
    female: int


class DemographicsResponse(BaseModel):
    release_id: int
    release_key: str
    dataset_fingerprint: str
    source_name: str
    source_url: str
    observed_at: date | None
    total_areas: int
    covered_areas: int
    total_population: int
    male: int
    female: int
    age_gender: list[AgeGenderBand]
    areas: list[DemographicArea]
