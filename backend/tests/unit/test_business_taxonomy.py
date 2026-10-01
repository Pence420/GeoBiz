import pytest

from app.taxonomy.businesses import (
    TAXONOMY_VERSION,
    BusinessClassification,
    classify_business,
)


@pytest.mark.parametrize(
    ("tags", "category", "subtype"),
    [
        ({"amenity": "restaurant"}, "fnb", "restaurant"),
        ({"amenity": "cafe"}, "fnb", "cafe"),
        ({"amenity": "fast_food"}, "fnb", "fast_food"),
        ({"amenity": "food_court"}, "fnb", "food_court"),
        ({"shop": "bakery"}, "fnb", "bakery"),
        ({"shop": "confectionery"}, "fnb", "confectionery"),
        ({"shop": "deli"}, "fnb", "deli"),
        ({"shop": "coffee"}, "fnb", "coffee"),
        ({"shop": "ice_cream"}, "fnb", "ice_cream"),
        ({"shop": "supermarket"}, "retail", "supermarket"),
        ({"shop": "convenience"}, "retail", "convenience"),
        ({"shop": "department_store"}, "retail", "department_store"),
        ({"shop": "variety_store"}, "retail", "variety_store"),
        ({"shop": "clothes"}, "retail", "clothes"),
        ({"shop": "shoes"}, "retail", "shoes"),
        ({"shop": "electronics"}, "retail", "electronics"),
        ({"shop": "mobile_phone"}, "retail", "mobile_phone"),
        ({"shop": "furniture"}, "retail", "furniture"),
        ({"shop": "books"}, "retail", "books"),
        ({"shop": "stationery"}, "retail", "stationery"),
        ({"shop": "cosmetics"}, "retail", "cosmetics"),
        ({"shop": "jewelry"}, "retail", "jewellery"),
        ({"shop": "hardware"}, "retail", "hardware"),
        ({"shop": "sports"}, "retail", "sports"),
        ({"shop": "toys"}, "retail", "toys"),
        ({"shop": "pet"}, "retail", "pet"),
        ({"shop": "car"}, "retail", "car"),
        ({"shop": "motorcycle"}, "retail", "motorcycle"),
        ({"leisure": "fitness_centre"}, "services", "fitness_centre"),
        ({"amenity": "gym"}, "services", "gym"),
        ({"shop": "hairdresser"}, "services", "hairdresser"),
        ({"shop": "beauty"}, "services", "beauty"),
        (
            {"shop": "hairdresser", "hairdresser": "barber"},
            "services",
            "barbershop",
        ),
        ({"shop": "laundry"}, "services", "laundry"),
        ({"amenity": "car_wash"}, "services", "car_wash"),
        ({"shop": "car_repair"}, "services", "car_repair"),
        ({"shop": "motorcycle_repair"}, "services", "motorcycle_repair"),
        ({"shop": "bicycle_repair"}, "services", "bicycle_repair"),
        ({"shop": "travel_agency"}, "services", "travel_agency"),
        ({"shop": "copyshop"}, "services", "copy_shop"),
        ({"craft": "printer"}, "services", "printing"),
    ],
)
def test_classifies_supported_business(
    tags: dict[str, str], category: str, subtype: str
) -> None:
    assert classify_business(tags) == BusinessClassification(category, subtype)


@pytest.mark.parametrize(
    "tags",
    [
        {"amenity": "pharmacy"},
        {"amenity": "clinic"},
        {"amenity": "school"},
        {"office": "company"},
        {"tourism": "hotel"},
        {"shop": "yes"},
        {"amenity": "place_of_worship"},
        {"industrial": "factory"},
        {"shop": "unknown_value"},
    ],
)
def test_rejects_unsupported_business(tags: dict[str, str]) -> None:
    assert classify_business(tags) is None


def test_explicit_priority_resolves_supported_multi_match() -> None:
    result = classify_business({"amenity": "cafe", "shop": "bakery"})
    assert result == BusinessClassification("fnb", "cafe")


def test_cross_category_ambiguity_is_rejected() -> None:
    result = classify_business(
        {"shop": "supermarket", "leisure": "fitness_centre"}
    )
    assert result is None


def test_taxonomy_version_is_pinned() -> None:
    assert TAXONOMY_VERSION == "v2.0.0"
