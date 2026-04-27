from rest_framework import serializers

from ..models import Category
from ..services.cloudinary_assets import CATALOG_CATEGORY_PREFIXES
from .base import UUIDSerializer
from .cloudinary_mixin import CloudinaryMediaMixin


class CategorySerializer(CloudinaryMediaMixin, UUIDSerializer):
    image_ref = serializers.JSONField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="Cloudinary ref: {'public_id': '...'} or string, or null to clear",
    )

    class Meta:
        model = Category
        fields = "__all__"

    def create(self, validated_data):
        image_ref = self._pop_optional_input(validated_data, "image_ref")
        category = super().create(validated_data)
        if self._apply_image_input(
            category,
            "image",
            image_ref,
            CATALOG_CATEGORY_PREFIXES,
        ):
            category.save(update_fields=["image"])
        return category

    def update(self, instance, validated_data):
        image_ref = self._pop_optional_input(validated_data, "image_ref")
        category = super().update(instance, validated_data)
        if self._apply_image_input(
            category,
            "image",
            image_ref,
            CATALOG_CATEGORY_PREFIXES,
        ):
            category.save(update_fields=["image"])
        return category
