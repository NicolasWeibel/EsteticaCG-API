"""Shared Cloudinary folder prefixes used by catalog and waxing serializers."""

CATALOG_MEDIA_PREFIXES = ["catalog/treatments", "catalog/combos", "catalog/journeys"]
CATALOG_IMAGE_PREFIXES = ["catalog/items/benefits", "catalog/items/recommended"]
CATALOG_CATEGORY_PREFIXES = ["catalog/categories"]
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
    "CATALOG_CATEGORY_PREFIXES",
    "WAXING_PREFIXES",
]
