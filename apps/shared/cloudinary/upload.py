"""
Cloudinary direct upload service.

This module provides backend-assisted signing for direct client uploads to Cloudinary.
The approach ensures:
1. Files never pass through Django/Cloud Run (avoiding 413 errors)
2. All uploads are signed server-side (no unsigned uploads allowed)
3. Upload parameters are controlled by the backend
"""

import time
import uuid
from dataclasses import dataclass
from typing import Literal, Optional

from django.conf import settings
import cloudinary
import cloudinary.uploader
import cloudinary.utils


RESOURCE_TYPES = Literal["image", "video", "auto"]


# Allowed folders per resource context
ALLOWED_FOLDERS = {
    # Catalog
    "catalog_treatment_media": "catalog/treatments",
    "catalog_treatment_benefits": "catalog/items/benefits",
    "catalog_treatment_recommended": "catalog/items/recommended",
    "catalog_combo_media": "catalog/combos",
    "catalog_combo_benefits": "catalog/items/benefits",
    "catalog_combo_recommended": "catalog/items/recommended",
    "catalog_journey_media": "catalog/journeys",
    "catalog_journey_benefits": "catalog/items/benefits",
    "catalog_journey_recommended": "catalog/items/recommended",
    "catalog_category": "catalog/categories",
    # Waxing
    "waxing_content": "waxing/content",
    "waxing_section": "waxing/sections",
    "waxing_area_category": "waxing/area_categories",
    "waxing_area": "waxing/areas",
    "waxing_pack": "waxing/packs",
}

# Maximum allowed file sizes in bytes per context
MAX_FILE_SIZES = {
    "image": 10 * 1024 * 1024,  # 10 MB for images
    "video": 100 * 1024 * 1024,  # 100 MB for videos
}

# Allowed file formats
ALLOWED_FORMATS = {
    "image": ["jpg", "jpeg", "png", "webp", "gif"],
    "video": ["mp4", "mov", "webm", "m4v", "avi"],
}


@dataclass
class UploadParams:
    """Parameters returned for client-side direct upload."""

    signature: str
    timestamp: int
    cloud_name: str
    api_key: str
    folder: str
    public_id: str
    final_public_id: str
    resource_type: str
    allowed_formats: list[str]
    max_file_size: int
    upload_url: str


def _get_cloudinary_config():
    """Get Cloudinary configuration from Django settings."""
    storage_config = getattr(settings, "CLOUDINARY_STORAGE", {})
    return {
        "cloud_name": storage_config.get("CLOUD_NAME", ""),
        "api_key": storage_config.get("API_KEY", ""),
        "api_secret": storage_config.get("API_SECRET", ""),
    }


def _generate_public_id(original_filename: Optional[str] = None) -> str:
    """Generate a unique base public_id for the upload."""
    suffix = uuid.uuid4().hex[:8]
    if original_filename:
        # Clean the filename
        import os

        base_name = os.path.splitext(original_filename)[0]
        # Remove problematic characters
        clean_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in base_name)[
            :50
        ]
        return f"{clean_name}-{suffix}"
    return f"upload-{suffix}"


def generate_upload_signature(
    context: str,
    resource_type: RESOURCE_TYPES = "auto",
    original_filename: Optional[str] = None,
    eager_transformations: Optional[list] = None,
) -> UploadParams:
    """
    Generate signed upload parameters for direct client upload to Cloudinary.

    Args:
        context: Upload context key (e.g., "catalog_treatment_media")
        resource_type: Type of resource ("image", "video", or "auto")
        original_filename: Optional original filename for naming
        eager_transformations: Optional list of eager transformations

    Returns:
        UploadParams with all data needed for client-side upload

    Raises:
        ValueError: If context is not allowed
    """
    if context not in ALLOWED_FOLDERS:
        raise ValueError(f"Invalid upload context: {context}")
    if resource_type not in ("image", "video", "auto"):
        raise ValueError(
            "Invalid resource_type. Allowed: ['image', 'video', 'auto']"
        )

    config = _get_cloudinary_config()
    folder_prefix = getattr(settings, "CLOUDINARY_STORAGE", {}).get("PREFIX", "")
    base_folder = ALLOWED_FOLDERS[context]
    full_folder = f"{folder_prefix}/{base_folder}" if folder_prefix else base_folder

    upload_public_id = _generate_public_id(original_filename)
    final_public_id = f"{full_folder}/{upload_public_id}"
    timestamp = int(time.time())

    # Determine resource type and constraints
    if resource_type == "auto":
        effective_resource_type = "auto"
        allowed_formats = ALLOWED_FORMATS["image"] + ALLOWED_FORMATS["video"]
        max_size = MAX_FILE_SIZES["video"]  # Use larger limit for auto
    else:
        effective_resource_type = resource_type
        allowed_formats = ALLOWED_FORMATS.get(resource_type, [])
        max_size = MAX_FILE_SIZES.get(resource_type, MAX_FILE_SIZES["image"])

    # Build parameters for signature
    params = {
        "timestamp": timestamp,
        "public_id": upload_public_id,
        "folder": full_folder,
    }

    if eager_transformations:
        params["eager"] = eager_transformations

    # Generate signature using Cloudinary SDK
    # The SDK handles proper sorting and string encoding
    cloudinary.config(
        cloud_name=config["cloud_name"],
        api_key=config["api_key"],
        api_secret=config["api_secret"],
    )
    signature = cloudinary.utils.api_sign_request(
        params,
        config["api_secret"],
    )

    upload_url = (
        f"https://api.cloudinary.com/v1_1/{config['cloud_name']}"
        f"/{effective_resource_type}/upload"
    )

    return UploadParams(
        signature=signature,
        timestamp=timestamp,
        cloud_name=config["cloud_name"],
        api_key=config["api_key"],
        folder=full_folder,
        public_id=upload_public_id,
        final_public_id=final_public_id,
        resource_type=effective_resource_type,
        allowed_formats=allowed_formats,
        max_file_size=max_size,
        upload_url=upload_url,
    )


def get_allowed_contexts():
    """Get list of allowed upload contexts."""
    return list(ALLOWED_FOLDERS.keys())


def validate_upload_context(context: str) -> str:
    """Validate an upload context and return it unchanged if valid."""
    if not context:
        raise ValueError("context is required")
    if context not in ALLOWED_FOLDERS:
        raise ValueError(f"Invalid context. Allowed: {list(ALLOWED_FOLDERS.keys())}")
    return context


def get_allowed_prefixes_for_context(context: str) -> list[str]:
    """Return the folder prefixes allowed for a validated upload context."""
    valid_context = validate_upload_context(context)
    return [ALLOWED_FOLDERS[valid_context]]


def normalize_destroy_result(provider_result: dict) -> tuple[str, str]:
    """
    Normalize Cloudinary destroy responses to API-facing statuses.

    Returns:
        Tuple of (status, provider_result_value)
    """
    raw_result = provider_result.get("result", "unknown")
    if raw_result == "ok":
        return "deleted", raw_result
    if raw_result == "not found":
        return "not_found", raw_result
    return "failed", raw_result


def delete_uploaded_asset(public_id: str, resource_type: str = "image") -> dict:
    """
    Delete a previously uploaded Cloudinary asset by public_id.

    Args:
        public_id: Exact Cloudinary public_id to delete.
        resource_type: "image" or "video".

    Returns:
        Raw Cloudinary destroy response.
    """
    config = _get_cloudinary_config()
    cloudinary.config(
        cloud_name=config["cloud_name"],
        api_key=config["api_key"],
        api_secret=config["api_secret"],
    )
    return cloudinary.uploader.destroy(public_id, resource_type=resource_type)
