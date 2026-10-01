from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

TAXONOMY_VERSION = "v2.0.0"
BusinessCategorySlug = Literal["fnb", "retail", "services"]


@dataclass(frozen=True)
class BusinessClassification:
    category_slug: BusinessCategorySlug
    subtype: str


@dataclass(frozen=True)
class BusinessRule:
    required_tags: tuple[tuple[str, str], ...]
    classification: BusinessClassification

    def matches(self, tags: Mapping[str, str]) -> bool:
        return all(tags.get(key) == value for key, value in self.required_tags)


def _rule(
    category: BusinessCategorySlug,
    subtype: str,
    **required_tags: str,
) -> BusinessRule:
    return BusinessRule(
        required_tags=tuple(required_tags.items()),
        classification=BusinessClassification(category, subtype),
    )


BUSINESS_RULES: tuple[BusinessRule, ...] = (
    # More-specific rules must precede their broader same-category rules.
    _rule("services", "barbershop", shop="hairdresser", hairdresser="barber"),
    _rule("fnb", "restaurant", amenity="restaurant"),
    _rule("fnb", "cafe", amenity="cafe"),
    _rule("fnb", "fast_food", amenity="fast_food"),
    _rule("fnb", "food_court", amenity="food_court"),
    _rule("fnb", "ice_cream", amenity="ice_cream"),
    _rule("fnb", "bakery", shop="bakery"),
    _rule("fnb", "confectionery", shop="confectionery"),
    _rule("fnb", "deli", shop="deli"),
    _rule("fnb", "coffee", shop="coffee"),
    _rule("fnb", "ice_cream", shop="ice_cream"),
    _rule("retail", "supermarket", shop="supermarket"),
    _rule("retail", "convenience", shop="convenience"),
    _rule("retail", "department_store", shop="department_store"),
    _rule("retail", "variety_store", shop="variety_store"),
    _rule("retail", "clothes", shop="clothes"),
    _rule("retail", "shoes", shop="shoes"),
    _rule("retail", "electronics", shop="electronics"),
    _rule("retail", "mobile_phone", shop="mobile_phone"),
    _rule("retail", "furniture", shop="furniture"),
    _rule("retail", "books", shop="books"),
    _rule("retail", "stationery", shop="stationery"),
    _rule("retail", "cosmetics", shop="cosmetics"),
    _rule("retail", "jewellery", shop="jewelry"),
    _rule("retail", "jewellery", shop="jewellery"),
    _rule("retail", "hardware", shop="hardware"),
    _rule("retail", "sports", shop="sports"),
    _rule("retail", "toys", shop="toys"),
    _rule("retail", "pet", shop="pet"),
    _rule("retail", "car", shop="car"),
    _rule("retail", "motorcycle", shop="motorcycle"),
    _rule("services", "fitness_centre", leisure="fitness_centre"),
    _rule("services", "gym", amenity="gym"),
    _rule("services", "hairdresser", shop="hairdresser"),
    _rule("services", "beauty", shop="beauty"),
    _rule("services", "laundry", shop="laundry"),
    _rule("services", "car_wash", amenity="car_wash"),
    _rule("services", "car_repair", shop="car_repair"),
    _rule("services", "motorcycle_repair", shop="motorcycle_repair"),
    _rule("services", "bicycle_repair", shop="bicycle_repair"),
    _rule("services", "travel_agency", shop="travel_agency"),
    _rule("services", "copy_shop", shop="copyshop"),
    _rule("services", "printing", craft="printer"),
)


def classify_business(
    tags: Mapping[str, str],
) -> BusinessClassification | None:
    matches = [rule.classification for rule in BUSINESS_RULES if rule.matches(tags)]
    categories = {match.category_slug for match in matches}
    if len(categories) != 1:
        return None
    return matches[0]
