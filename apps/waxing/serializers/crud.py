import json

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

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


class WaxingSettingsSerializer(ModelCleanValidationMixin, UUIDSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None and WaxingSettings.objects.exists():
            raise serializers.ValidationError(
                {"non_field_errors": ["Solo puede existir un registro de WaxingSettings."]}
            )
        return attrs

    class Meta:
        model = WaxingSettings
        fields = "__all__"


class SectionSerializer(ModelCleanValidationMixin, UUIDSerializer):
    class Meta:
        model = Section
        fields = "__all__"


class AreaCategorySerializer(ModelCleanValidationMixin, UUIDSerializer):
    class Meta:
        model = AreaCategory
        fields = "__all__"


class AreaSerializer(ModelCleanValidationMixin, UUIDSerializer):
    class Meta:
        model = Area
        fields = "__all__"


class PackSerializer(ModelCleanValidationMixin, UUIDSerializer):
    class Meta:
        model = Pack
        fields = "__all__"


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


class WaxingContentSerializer(ModelCleanValidationMixin, UUIDSerializer):
    benefits = BenefitItemNestedSerializer(many=True, required=False)
    recommendations = RecommendationItemNestedSerializer(many=True, required=False)
    faqs = FaqItemNestedSerializer(many=True, required=False)
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

    def _normalize_ordered_list(self, items, field_name, fill_missing_order):
        if items is None:
            return None
        if not isinstance(items, (list, tuple)):
            raise ValidationError({field_name: "Debe ser una lista."})

        normalized = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValidationError(
                    {field_name: "Cada elemento debe ser un objeto."}
                )
            if fill_missing_order and item.get("order") is None:
                item = {**item, "order": index}
            normalized.append(item)
        return normalized

    def _resequence_related_items(self, model_cls, content):
        qs = model_cls.objects.filter(content=content).order_by("order", "created_at", "id")
        to_update = []
        for index, obj in enumerate(qs):
            if obj.order != index:
                obj.order = index
                to_update.append(obj)
        if to_update:
            model_cls.objects.bulk_update(to_update, ["order"])

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
        if remove_ids:
            base_qs.filter(id__in=remove_ids).delete()

        if items is None:
            return

        normalized = self._normalize_ordered_list(items, field_name, fill_missing_order)
        if not normalized:
            return

        existing = list(base_qs)
        existing_map = {str(obj.id): obj for obj in existing}
        max_order = max([obj.order for obj in existing], default=-1)
        to_create = []
        to_update = []

        for item in normalized:
            item_id = item.get("id")
            payload = dict(item)
            payload.pop("id", None)

            if item_id:
                obj = existing_map.get(str(item_id))
                if not obj:
                    raise ValidationError(
                        {field_name: f"El id {item_id} no pertenece a este contenido."}
                    )
                if payload.get("order") is None:
                    payload.pop("order", None)
                for key, value in payload.items():
                    setattr(obj, key, value)
                to_update.append(obj)
            else:
                if payload.get("order") is None:
                    max_order += 1
                    payload["order"] = max_order
                to_create.append(model_cls(content=content, **payload))

        if to_create:
            model_cls.objects.bulk_create(to_create)
        if to_update:
            model_cls.objects.bulk_update(to_update, update_fields)
        self._resequence_related_items(model_cls, content)

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
                {"non_field_errors": ["Solo puede existir un registro de WaxingContent."]}
            )
        return attrs

    def create(self, validated_data):
        benefits = validated_data.pop("benefits", [])
        recommendations = validated_data.pop("recommendations", [])
        faqs = validated_data.pop("faqs", [])

        with transaction.atomic():
            content = super().create(validated_data)
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
        recommendations_remove_ids = validated_data.pop("recommendations_remove_ids", None)
        faqs_remove_ids = validated_data.pop("faqs_remove_ids", None)

        with transaction.atomic():
            content = super().update(instance, validated_data)
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
