from rest_framework import serializers

from ..models import (
    Technique,
    Objective,
    Intensity,
    Tag,
)
from ..services.cloudinary_assets import CATALOG_OBJECTIVE_PREFIXES
from .base import UUIDSerializer
from .cloudinary_mixin import CloudinaryMediaMixin


class TechniqueSerializer(UUIDSerializer):
    class Meta:
        model = Technique
        fields = "__all__"


class ObjectiveSerializer(CloudinaryMediaMixin, UUIDSerializer):
    image_ref = serializers.JSONField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="Cloudinary ref: {'public_id': '...'} or string, or null to clear",
    )

    class Meta:
        model = Objective
        fields = "__all__"

    def create(self, validated_data):
        image_ref = self._pop_optional_input(validated_data, "image_ref")
        objective = super().create(validated_data)
        if self._apply_image_input(
            objective,
            "image",
            image_ref,
            CATALOG_OBJECTIVE_PREFIXES,
        ):
            objective.save(update_fields=["image"])
        return objective

    def update(self, instance, validated_data):
        image_ref = self._pop_optional_input(validated_data, "image_ref")
        objective = super().update(instance, validated_data)
        if self._apply_image_input(
            objective,
            "image",
            image_ref,
            CATALOG_OBJECTIVE_PREFIXES,
        ):
            objective.save(update_fields=["image"])
        return objective


class IntensitySerializer(UUIDSerializer):
    class Meta:
        model = Intensity
        fields = "__all__"


class TagSerializer(UUIDSerializer):
    class Meta:
        model = Tag
        fields = "__all__"
