"""Shared Cloudinary folder prefixes used by catalog and waxing serializers."""

CATALOG_MEDIA_PREFIXES = ["catalog/treatments", "catalog/combos", "catalog/journeys"]
CATALOG_IMAGE_PREFIXES = ["catalog/items/benefits", "catalog/items/recommended"]
CATALOG_JOURNEY_IMAGE_PREFIXES = [
    "catalog/journeys/benefits",
    "catalog/journeys/recommended",
]
CATALOG_CATEGORY_PREFIXES = ["catalog/categories"]
CATALOG_OBJECTIVE_PREFIXES = ["catalog/filters/objectives"]
WAXING_PREFIXES = [
    "waxing/content",
    "waxing/sections",
    "waxing/area_categories",
    "waxing/areas",
    "waxing/packs",
]

__all__ = [
    "CATALOG_MEDIA_PREFIXES",
    "CATALOG_IMAGE_PREFIXES",
    "CATALOG_JOURNEY_IMAGE_PREFIXES",
    "CATALOG_CATEGORY_PREFIXES",
    "CATALOG_OBJECTIVE_PREFIXES",
    "WAXING_PREFIXES",
]
