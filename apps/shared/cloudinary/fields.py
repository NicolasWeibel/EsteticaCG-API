"""
Cloudinary serializer fields for DRF.

These fields handle the validation and transformation of Cloudinary asset
references in API requests.
"""

from typing import Optional

from rest_framework import serializers

from .validation import (
    validate_cloudinary_asset,
    CloudinaryAssetRef,
    CloudinaryValidationError,
)


class CloudinaryAssetField(serializers.Field):
    """
    Serializer field for Cloudinary asset references.

    Accepts:
    - {"public_id": "folder/name", "resource_type": "image|video"}
    - {"public_id": "folder/name"}
    - {"url": "https://res.cloudinary.com/..."}
    - String public_id directly
    - String URL directly
    - None / null (if allow_null=True)

    Returns on read:
    - Full Cloudinary URL for the asset
    """

    def __init__(
        self,
        allowed_prefixes: list[str],
        resource_type: str = "auto",
        verify_exists: bool = False,
        **kwargs,
    ):
        """
        Args:
            allowed_prefixes: List of allowed folder prefixes (without global prefix)
            resource_type: Expected resource type ("image", "video", or "auto")
            verify_exists: Whether to verify asset exists via API
        """
        self.allowed_prefixes = allowed_prefixes
        self.expected_resource_type = resource_type
        self.verify_exists = verify_exists
        super().__init__(**kwargs)

    def to_internal_value(self, data) -> Optional[CloudinaryAssetRef]:
        """Transform input to CloudinaryAssetRef."""
        if data is None or data == "":
            if self.allow_null:
                return None
            raise serializers.ValidationError("This field cannot be null.")

        # Handle string input (public_id or URL)
        if isinstance(data, str):
            data = {"public_id": data}

        try:
            return validate_cloudinary_asset(
                reference=data,
                allowed_prefixes=self.allowed_prefixes,
                verify_exists=self.verify_exists,
            )
        except CloudinaryValidationError as e:
            raise serializers.ValidationError(str(e))

    def to_representation(self, value) -> Optional[str]:
        """Transform stored value to URL for API response."""
        if not value:
            return None

        # value is the public_id stored in FileField/ImageField
        if hasattr(value, "url"):
            return value.url

        # Direct string public_id
        from .validation import build_cloudinary_url

        return build_cloudinary_url(str(value))


class CloudinaryImageField(CloudinaryAssetField):
    """Specialized field for image assets only."""

    def __init__(self, allowed_prefixes: list[str], **kwargs):
        kwargs.setdefault("resource_type", "image")
        super().__init__(allowed_prefixes=allowed_prefixes, **kwargs)


class CloudinaryVideoField(CloudinaryAssetField):
    """Specialized field for video assets only."""

    def __init__(self, allowed_prefixes: list[str], **kwargs):
        kwargs.setdefault("resource_type", "video")
        super().__init__(allowed_prefixes=allowed_prefixes, **kwargs)


class CloudinaryMediaField(CloudinaryAssetField):
    """Field that accepts both images and videos (auto-detect)."""

    def __init__(self, allowed_prefixes: list[str], **kwargs):
        kwargs.setdefault("resource_type", "auto")
        super().__init__(allowed_prefixes=allowed_prefixes, **kwargs)


class CloudinaryGalleryItemField(serializers.Serializer):
    """
    Serializer for gallery items that can be existing media or new uploads.

    Accepts:
    - {"id": "<uuid>"} - Reference to existing media item
    - {"public_id": "...", "resource_type": "image|video"} - New Cloudinary upload
    - {"upload_key": "...", "public_id": "...", "resource_type": "..."} - New upload with client key
    """

    id = serializers.UUIDField(required=False, allow_null=True)
    upload_key = serializers.CharField(required=False, allow_blank=True)
    public_id = serializers.CharField(required=False, allow_blank=True)
    resource_type = serializers.ChoiceField(
        choices=["image", "video"],
        required=False,
        default="image",
    )
    alt_text = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        """Ensure either id or public_id is provided."""
        has_id = attrs.get("id")
        has_public_id = attrs.get("public_id")

        if not has_id and not has_public_id:
            raise serializers.ValidationError(
                "Each item must have either 'id' (existing) or 'public_id' (new upload)"
            )

        if has_id and has_public_id:
            raise serializers.ValidationError(
                "Provide either 'id' or 'public_id', not both"
            )

        return attrs
