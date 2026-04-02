"""
Waxing CRUD serializers with JSON-only Cloudinary image support.
"""

import json

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.shared.serializers.ordered_items import OrderedNestedItemsMixin
from apps.shared.cloudinary import (
    validate_cloudinary_asset,
    CloudinaryValidationError,
)

from ..models import (
    Area,
    AreaCategory,
    BenefitItem,
    FaqItem,
    FeaturedItemOrder,
    Pack,
    PackArea,
    RecommendationItem,
    Section,
    WaxingContent,
    WaxingSettings,
)
from .common import ModelCleanValidationMixin, UUIDSerializer


class CloudinaryImageRefMixin:
    """
    Mixin for serializers that handle a single Cloudinary image via JSON reference.
    """

    def _pop_optional_input(self, validated_data: dict, key: str):
        if key not in validated_data:
            return serializers.empty
        return validated_data.pop(key)

    def _handle_image_ref(self, instance, field_name: str, value, allowed_prefixes: list[str]):
        """
        Handle image field input that could be:
        - None: leave unchanged
        - "": clear the field
        - string public_id: validate and set
        - dict with public_id: validate and set
        """
        if value is serializers.empty:
            return False

        if value is None or value == "" or value == {}:
            setattr(instance, field_name, None)
            return True

        # Accept string public_id directly
        if isinstance(value, str):
            ref_data = {"public_id": value}
        else:
            ref_data = value

        try:
            ref = validate_cloudinary_asset(
                reference=ref_data,
                allowed_prefixes=allowed_prefixes,
            )
            setattr(instance, field_name, ref.public_id)
            return True
        except CloudinaryValidationError as e:
            raise ValidationError({field_name: str(e)})


class WaxingSettingsSerializer(ModelCleanValidationMixin, UUIDSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None and WaxingSettings.objects.exists():
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Solo puede existir un registro de WaxingSettings."
                    ]
                }
            )
        return attrs

    class Meta:
        model = WaxingSettings
        fields = "__all__"


class SectionSerializer(
    CloudinaryImageRefMixin, ModelCleanValidationMixin, UUIDSerializer
):
    image_ref = serializers.JSONField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="Cloudinary ref: {'public_id': '...'} or string, or null to clear",
    )

    class Meta:
        model = Section
        fields = "__all__"

    def create(self, validated_data):
        image_ref = self._pop_optional_input(validated_data, "image_ref")
        instance = super().create(validated_data)
        if self._handle_image_ref(instance, "image", image_ref, ["waxing/sections"]):
            instance.save(update_fields=["image"])
        return instance

    def update(self, instance, validated_data):
        image_ref = self._pop_optional_input(validated_data, "image_ref")
        instance = super().update(instance, validated_data)
        if self._handle_image_ref(instance, "image", image_ref, ["waxing/sections"]):
            instance.save(update_fields=["image"])
        return instance


class AreaCategorySerializer(
    CloudinaryImageRefMixin, ModelCleanValidationMixin, UUIDSerializer
):
    image_ref = serializers.JSONField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="Cloudinary ref: {'public_id': '...'} or string, or null to clear",
    )

    class Meta:
        model = AreaCategory
        fields = "__all__"

    def create(self, validated_data):
        image_ref = self._pop_optional_input(validated_data, "image_ref")
        instance = super().create(validated_data)
        if self._handle_image_ref(instance, "image", image_ref, ["waxing/area_categories"]):
            instance.save(update_fields=["image"])
        return instance

    def update(self, instance, validated_data):
        image_ref = self._pop_optional_input(validated_data, "image_ref")
        instance = super().update(instance, validated_data)
        if self._handle_image_ref(instance, "image", image_ref, ["waxing/area_categories"]):
            instance.save(update_fields=["image"])
        return instance


class AreaSerializer(
    CloudinaryImageRefMixin, ModelCleanValidationMixin, UUIDSerializer
):
    image_ref = serializers.JSONField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="Cloudinary ref: {'public_id': '...'} or string, or null to clear",
    )

    class Meta:
        model = Area
        fields = "__all__"

    def create(self, validated_data):
        image_ref = self._pop_optional_input(validated_data, "image_ref")
        instance = super().create(validated_data)
        if self._handle_image_ref(instance, "image", image_ref, ["waxing/areas"]):
            instance.save(update_fields=["image"])
        return instance

    def update(self, instance, validated_data):
        image_ref = self._pop_optional_input(validated_data, "image_ref")
        instance = super().update(instance, validated_data)
        if self._handle_image_ref(instance, "image", image_ref, ["waxing/areas"]):
            instance.save(update_fields=["image"])
        return instance


class PackSerializer(
    CloudinaryImageRefMixin, ModelCleanValidationMixin, UUIDSerializer
):
    image_ref = serializers.JSONField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="Cloudinary ref: {'public_id': '...'} or string, or null to clear",
    )

    class Meta:
        model = Pack
        fields = "__all__"

    def create(self, validated_data):
        image_ref = self._pop_optional_input(validated_data, "image_ref")
        instance = super().create(validated_data)
        if self._handle_image_ref(instance, "image", image_ref, ["waxing/packs"]):
            instance.save(update_fields=["image"])
        return instance

    def update(self, instance, validated_data):
        image_ref = self._pop_optional_input(validated_data, "image_ref")
        instance = super().update(instance, validated_data)
        if self._handle_image_ref(instance, "image", image_ref, ["waxing/packs"]):
            instance.save(update_fields=["image"])
        return instance


class PackAreaSerializer(ModelCleanValidationMixin, UUIDSerializer):
    class Meta:
        model = PackArea
        fields = "__all__"


class FeaturedItemOrderSerializer(ModelCleanValidationMixin, UUIDSerializer):
    class Meta:
        model = FeaturedItemOrder
        fields = "__all__"


class BenefitItemNestedSerializer(UUIDSerializer):
    id = serializers.UUIDField(required=False)

    class Meta:
        model = BenefitItem
        fields = ("id", "title", "detail", "order", "is_active")
        extra_kwargs = {
            "order": {"required": False},
            "is_active": {"required": False},
        }


class RecommendationItemNestedSerializer(UUIDSerializer):
    id = serializers.UUIDField(required=False)

    class Meta:
        model = RecommendationItem
        fields = ("id", "title", "detail", "order", "is_active")
        extra_kwargs = {
            "order": {"required": False},
            "is_active": {"required": False},
        }


class FaqItemNestedSerializer(UUIDSerializer):
    id = serializers.UUIDField(required=False)

    class Meta:
        model = FaqItem
        fields = ("id", "question", "answer", "order", "is_active")
        extra_kwargs = {
            "order": {"required": False},
            "is_active": {"required": False},
        }


class WaxingContentSerializer(
    CloudinaryImageRefMixin,
    ModelCleanValidationMixin,
    OrderedNestedItemsMixin,
    UUIDSerializer,
):
    """
    WaxingContent serializer with JSON-only Cloudinary image support.

    Image handling:
    - Use `image_ref`, `benefits_image_ref`, `recommendations_image_ref`
    - All image references must be Cloudinary public_ids from signed uploads
    """

    benefits = BenefitItemNestedSerializer(many=True, required=False)
    recommendations = RecommendationItemNestedSerializer(many=True, required=False)
    faqs = FaqItemNestedSerializer(many=True, required=False)

    # JSON-only image fields
    image_ref = serializers.JSONField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="Cloudinary ref: {'public_id': '...'} or string, or null to clear",
    )
    benefits_image_ref = serializers.JSONField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="Cloudinary ref: {'public_id': '...'} or string, or null to clear",
    )
    recommendations_image_ref = serializers.JSONField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="Cloudinary ref: {'public_id': '...'} or string, or null to clear",
    )

    # Removal fields for nested content
    benefits_remove_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )
    recommendations_remove_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )
    faqs_remove_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )

    def _parse_json_list(self, raw, field_name):
        if raw is None:
            return None
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception as exc:
                raise ValidationError({field_name: f"JSON invalido: {exc}"})
        if hasattr(raw, "read"):
            try:
                content = raw.read()
                if hasattr(raw, "seek"):
                    raw.seek(0)
                return json.loads(content)
            except Exception as exc:
                raise ValidationError({field_name: f"JSON invalido: {exc}"})
        return raw

    def _apply_related_changes(
        self,
        *,
        content,
        model_cls,
        items,
        remove_ids,
        field_name,
        update_fields,
        fill_missing_order,
    ):
        base_qs = model_cls.objects.filter(content=content)
        self._apply_ordered_changes(
            base_qs=base_qs,
            model_cls=model_cls,
            items=items,
            remove_ids=remove_ids,
            field_name=field_name,
            update_fields=update_fields,
            fill_missing_order=fill_missing_order,
            create_instance=lambda payload: model_cls(content=content, **payload),
            not_found_error="El id {item_id} no pertenece a este contenido.",
            list_error="Debe ser una lista.",
            object_error="Cada elemento debe ser un objeto.",
        )

    def to_internal_value(self, data):
        mutable = data.copy()
        for field_name in (
            "benefits",
            "recommendations",
            "faqs",
            "benefits_remove_ids",
            "recommendations_remove_ids",
            "faqs_remove_ids",
        ):
            if field_name in mutable:
                mutable[field_name] = self._parse_json_list(
                    mutable.get(field_name), field_name
                )
        return super().to_internal_value(mutable)

    def validate(self, attrs):
        deferred_keys = (
            "benefits",
            "recommendations",
            "faqs",
            "benefits_remove_ids",
            "recommendations_remove_ids",
            "faqs_remove_ids",
        )
        deferred_attrs = {key: attrs.pop(key) for key in deferred_keys if key in attrs}

        attrs = super().validate(attrs)
        attrs.update(deferred_attrs)

        if self.instance is None and WaxingContent.objects.exists():
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Solo puede existir un registro de WaxingContent."
                    ]
                }
            )
        return attrs

    def create(self, validated_data):
        benefits = validated_data.pop("benefits", [])
        recommendations = validated_data.pop("recommendations", [])
        faqs = validated_data.pop("faqs", [])

        # Extract image refs before create
        image_ref = self._pop_optional_input(validated_data, "image_ref")
        benefits_image_ref = self._pop_optional_input(
            validated_data, "benefits_image_ref"
        )
        recommendations_image_ref = self._pop_optional_input(
            validated_data, "recommendations_image_ref"
        )

        with transaction.atomic():
            content = super().create(validated_data)

            # Apply image references
            update_fields = []
            if self._handle_image_ref(content, "image", image_ref, ["waxing/content"]):
                update_fields.append("image")
            if self._handle_image_ref(
                    content, "benefits_image", benefits_image_ref, ["waxing/content"]
                ):
                update_fields.append("benefits_image")
            if self._handle_image_ref(
                    content,
                    "recommendations_image",
                    recommendations_image_ref,
                    ["waxing/content"],
                ):
                update_fields.append("recommendations_image")
            if update_fields:
                content.save(update_fields=update_fields)

            self._apply_related_changes(
                content=content,
                model_cls=BenefitItem,
                items=benefits,
                remove_ids=[],
                field_name="benefits",
                update_fields=["title", "detail", "order", "is_active"],
                fill_missing_order=True,
            )
            self._apply_related_changes(
                content=content,
                model_cls=RecommendationItem,
                items=recommendations,
                remove_ids=[],
                field_name="recommendations",
                update_fields=["title", "detail", "order", "is_active"],
                fill_missing_order=True,
            )
            self._apply_related_changes(
                content=content,
                model_cls=FaqItem,
                items=faqs,
                remove_ids=[],
                field_name="faqs",
                update_fields=["question", "answer", "order", "is_active"],
                fill_missing_order=True,
            )
            return content

    def update(self, instance, validated_data):
        benefits = validated_data.pop("benefits", None)
        recommendations = validated_data.pop("recommendations", None)
        faqs = validated_data.pop("faqs", None)
        benefits_remove_ids = validated_data.pop("benefits_remove_ids", None)
        recommendations_remove_ids = validated_data.pop(
            "recommendations_remove_ids", None
        )
        faqs_remove_ids = validated_data.pop("faqs_remove_ids", None)

        # Extract image refs
        image_ref = self._pop_optional_input(validated_data, "image_ref")
        benefits_image_ref = self._pop_optional_input(
            validated_data, "benefits_image_ref"
        )
        recommendations_image_ref = self._pop_optional_input(
            validated_data, "recommendations_image_ref"
        )

        with transaction.atomic():
            content = super().update(instance, validated_data)

            # Apply image references
            update_fields = []
            if self._handle_image_ref(content, "image", image_ref, ["waxing/content"]):
                update_fields.append("image")
            if self._handle_image_ref(
                    content, "benefits_image", benefits_image_ref, ["waxing/content"]
                ):
                update_fields.append("benefits_image")
            if self._handle_image_ref(
                    content,
                    "recommendations_image",
                    recommendations_image_ref,
                    ["waxing/content"],
                ):
                update_fields.append("recommendations_image")
            if update_fields:
                content.save(update_fields=update_fields)

            self._apply_related_changes(
                content=content,
                model_cls=BenefitItem,
                items=benefits,
                remove_ids=benefits_remove_ids,
                field_name="benefits",
                update_fields=["title", "detail", "order", "is_active"],
                fill_missing_order=False,
            )
            self._apply_related_changes(
                content=content,
                model_cls=RecommendationItem,
                items=recommendations,
                remove_ids=recommendations_remove_ids,
                field_name="recommendations",
                update_fields=["title", "detail", "order", "is_active"],
                fill_missing_order=False,
            )
            self._apply_related_changes(
                content=content,
                model_cls=FaqItem,
                items=faqs,
                remove_ids=faqs_remove_ids,
                field_name="faqs",
                update_fields=["question", "answer", "order", "is_active"],
                fill_missing_order=False,
            )
            return content

    class Meta:
        model = WaxingContent
        fields = "__all__"


class BenefitItemSerializer(ModelCleanValidationMixin, UUIDSerializer):
    class Meta:
        model = BenefitItem
        fields = "__all__"


class RecommendationItemSerializer(ModelCleanValidationMixin, UUIDSerializer):
    class Meta:
        model = RecommendationItem
        fields = "__all__"


class FaqItemSerializer(ModelCleanValidationMixin, UUIDSerializer):
    class Meta:
        model = FaqItem
        fields = "__all__"


class WaxingPublicQuerySerializer(serializers.Serializer):
    section = serializers.CharField(required=False, allow_blank=False, max_length=120)


class UUIDReorderSerializer(serializers.Serializer):
    items = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=True,
    )

    def validate_items(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError("No se permiten ids duplicados.")
        return value


class FeaturedReorderItemSerializer(serializers.Serializer):
    item_kind = serializers.ChoiceField(choices=FeaturedItemOrder.ItemKind.choices)
    item_id = serializers.UUIDField()


class FeaturedReorderSerializer(serializers.Serializer):
    items = FeaturedReorderItemSerializer(many=True, allow_empty=True)

    def validate_items(self, value):
        seen = set()
        for row in value:
            key = (row["item_kind"], row["item_id"])
            if key in seen:
                raise serializers.ValidationError("No se permiten items duplicados.")
            seen.add(key)
        return value
