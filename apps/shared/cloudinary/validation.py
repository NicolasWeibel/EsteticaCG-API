"""
Cloudinary asset validation service.

This module validates that Cloudinary asset references received from the frontend:
1. Belong to our Cloudinary account
2. Have public_ids within allowed folder prefixes
3. Actually exist in Cloudinary (optional API verification)
4. Have correct resource types
"""

import re
from dataclasses import dataclass
from typing import Literal, Optional

from django.conf import settings
import cloudinary
import cloudinary.api


class CloudinaryValidationError(Exception):
    """Raised when a Cloudinary asset fails validation."""

    pass


@dataclass
class CloudinaryAssetRef:
    """Validated Cloudinary asset reference."""

    public_id: str
    resource_type: Literal["image", "video"]
    format: Optional[str] = None
    version: Optional[str] = None
    secure_url: Optional[str] = None


# Regex to extract public_id from Cloudinary URL
CLOUDINARY_URL_PATTERN = re.compile(
    r"https?://res\.cloudinary\.com/(?P<cloud>[^/]+)/"
    r"(?P<resource_type>image|video|raw)/"
    r"upload/"
    r"(?:v(?P<version>\d+)/)?"
    r"(?P<public_id>.+?)(?:\.[a-zA-Z0-9]+)?$"
)


def _get_cloudinary_config():
    """Get Cloudinary configuration from Django settings."""
    storage_config = getattr(settings, "CLOUDINARY_STORAGE", {})
    return {
        "cloud_name": storage_config.get("CLOUD_NAME", ""),
        "api_key": storage_config.get("API_KEY", ""),
        "api_secret": storage_config.get("API_SECRET", ""),
        "prefix": storage_config.get("PREFIX", ""),
    }


def _normalize_public_id(value: str) -> tuple[str, Optional[str]]:
    """
    Normalize a public_id or URL to just the public_id.

    Returns:
        Tuple of (public_id, resource_type_from_url or None)
    """
    if not value:
        raise CloudinaryValidationError("Empty asset reference")

    # Check if it's a URL
    if value.startswith("http://") or value.startswith("https://"):
        match = CLOUDINARY_URL_PATTERN.match(value)
        if not match:
            raise CloudinaryValidationError("Invalid Cloudinary URL format")

        config = _get_cloudinary_config()
        if match.group("cloud") != config["cloud_name"]:
            raise CloudinaryValidationError(
                "Asset URL does not belong to authorized Cloudinary account"
            )

        public_id = match.group("public_id")
        resource_type = match.group("resource_type")
        return public_id, resource_type

    # Otherwise treat as public_id directly
    return value, None


def _validate_folder_prefix(public_id: str, allowed_prefixes: list[str]) -> bool:
    """
    Validate that public_id is within allowed folder prefixes.

    Args:
        public_id: The Cloudinary public_id
        allowed_prefixes: List of allowed folder prefixes (will be joined with global prefix)

    Returns:
        True if valid
    """
    config = _get_cloudinary_config()
    global_prefix = config.get("prefix", "")

    for prefix in allowed_prefixes:
        full_prefix = f"{global_prefix}/{prefix}" if global_prefix else prefix
        if public_id == full_prefix or public_id.startswith(f"{full_prefix}/"):
            return True

    return False


def _verify_asset_exists(
    public_id: str, resource_type: str = "image"
) -> Optional[dict]:
    """
    Verify asset exists in Cloudinary via API call.

    Args:
        public_id: The Cloudinary public_id
        resource_type: "image" or "video"

    Returns:
        Asset metadata dict if exists, None otherwise
    """
    config = _get_cloudinary_config()
    cloudinary.config(
        cloud_name=config["cloud_name"],
        api_key=config["api_key"],
        api_secret=config["api_secret"],
    )

    try:
        result = cloudinary.api.resource(public_id, resource_type=resource_type)
        return result
    except cloudinary.api.NotFound:
        return None
    except Exception:
        # Network errors, etc. - fail open but log
        return None


def validate_cloudinary_public_id(
    public_id: str,
    allowed_prefixes: list[str],
    resource_type: Literal["image", "video", "auto"] = "auto",
    verify_exists: bool = False,
) -> CloudinaryAssetRef:
    """
    Validate a Cloudinary public_id reference.

    Args:
        public_id: The public_id (can also be full Cloudinary URL)
        allowed_prefixes: List of allowed folder prefixes within the global prefix
        resource_type: Expected resource type, or "auto" to detect
        verify_exists: Whether to verify asset exists via API call

    Returns:
        CloudinaryAssetRef with validated data

    Raises:
        CloudinaryValidationError: If validation fails
    """
    # Normalize to public_id
    normalized_id, url_resource_type = _normalize_public_id(public_id)

    # Validate folder prefix
    if not _validate_folder_prefix(normalized_id, allowed_prefixes):
        raise CloudinaryValidationError(
            f"Asset public_id is not in an allowed folder. "
            f"Expected prefixes: {allowed_prefixes}"
        )

    # Determine resource type
    final_resource_type: Literal["image", "video"]
    if resource_type != "auto":
        final_resource_type = resource_type
    elif url_resource_type:
        final_resource_type = url_resource_type  # type: ignore
    else:
        # Default to image if not specified
        final_resource_type = "image"

    # Optional: Verify asset exists
    if verify_exists:
        metadata = _verify_asset_exists(normalized_id, final_resource_type)
        if metadata is None:
            raise CloudinaryValidationError(
                f"Asset not found in Cloudinary: {normalized_id}"
            )

    return CloudinaryAssetRef(
        public_id=normalized_id,
        resource_type=final_resource_type,
    )


def validate_cloudinary_asset(
    reference: dict,
    allowed_prefixes: list[str],
    verify_exists: bool = False,
) -> CloudinaryAssetRef:
    """
    Validate a Cloudinary asset reference dict from API request.

    Expected formats:
    - {"public_id": "folder/name", "resource_type": "image|video"}
    - {"public_id": "folder/name"}  # defaults to image
    - {"url": "https://res.cloudinary.com/..."}  # extracts public_id

    Args:
        reference: Dict with asset reference data
        allowed_prefixes: List of allowed folder prefixes
        verify_exists: Whether to verify asset exists

    Returns:
        CloudinaryAssetRef with validated data

    Raises:
        CloudinaryValidationError: If validation fails
    """
    if not isinstance(reference, dict):
        raise CloudinaryValidationError("Asset reference must be an object")

    # Accept either public_id or url
    public_id = reference.get("public_id") or reference.get("url")
    if not public_id:
        raise CloudinaryValidationError(
            "Asset reference must include 'public_id' or 'url'"
        )

    resource_type = reference.get("resource_type", "auto")
    if resource_type not in ("image", "video", "auto"):
        raise CloudinaryValidationError(f"Invalid resource_type: {resource_type}")

    return validate_cloudinary_public_id(
        public_id=public_id,
        allowed_prefixes=allowed_prefixes,
        resource_type=resource_type,
        verify_exists=verify_exists,
    )


def build_cloudinary_url(
    public_id: str,
    resource_type: str = "image",
    secure: bool = True,
    **transformations,
) -> str:
    """
    Build a Cloudinary URL from a public_id.

    This is a utility for reconstructing URLs when needed.
    """
    config = _get_cloudinary_config()
    url, _ = cloudinary.utils.cloudinary_url(
        public_id,
        cloud_name=config["cloud_name"],
        resource_type=resource_type,
        secure=secure,
        **transformations,
    )
    return url
