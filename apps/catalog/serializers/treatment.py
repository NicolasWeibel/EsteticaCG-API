"""
Treatment serializers with JSON-only Cloudinary media support.

This module has been migrated to accept only JSON requests with Cloudinary
asset references instead of multipart file uploads.
"""

import json
from django.db import transaction
from django.db.models import Avg
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ..models import (
    Treatment,
    TreatmentMedia,
    TreatmentZoneConfig,
    Combo,
    ItemBenefit,
    ItemRecommendedPoint,
    ItemFAQ,
)
from ..services.pricing import effective_price_for_treatment
from ..services.commands import cleanup_treatment_deactivation
from ..services.uniqueness import validate_item_uniqueness
from ..services.validation import validate_treatment_rules
from ..services.cloudinary_assets import CATALOG_MEDIA_PREFIXES, CATALOG_IMAGE_PREFIXES
from ..utils.media import build_media_url
from .gallery import TreatmentMediaSerializer
from .item_content import (
    ItemBenefitSerializer,
    ItemRecommendedPointSerializer,
    ItemFAQSerializer,
)
from .treatmentzoneconfig import TreatmentZoneConfigSerializer
from .fields import TagListField
from .base import UUIDSerializer
from .cloudinary_mixin import CloudinaryMediaMixin
from .utils import parse_json_list
from .item_content_sync import GenericItemContentSyncMixin
from .filters import TechniqueSerializer, ObjectiveSerializer, IntensitySerializer


class TreatmentSerializer(
    GenericItemContentSyncMixin, CloudinaryMediaMixin, UUIDSerializer
):
    """
    Treatment serializer with JSON-only Cloudinary media support.

    Media handling:
    - Use `media_items` to manage gallery (create, reorder, delete)
    - Use `benefits_image_ref` and `recommended_image_ref` for single images
    - All media references must be Cloudinary public_ids from signed uploads
    """

    zone_configs = TreatmentZoneConfigSerializer(many=True, required=False)
    media = TreatmentMediaSerializer(many=True, read_only=True)
    benefits = ItemBenefitSerializer(many=True, required=False)
    recommended_points = ItemRecommendedPointSerializer(many=True, required=False)
    faqs = ItemFAQSerializer(many=True, required=False)
    tags = TagListField(required=False)
    cover_media = serializers.SerializerMethodField()
    effective_price = serializers.SerializerMethodField()
    kind = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()

    # JSON-only media fields
    media_items = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text=(
            "Complete ordered gallery list. Format: "
            "[{'id': 'uuid'}, {'public_id': '...', 'resource_type': 'image|video'}, "
            "{'id': 'uuid', 'remove': true}]. Existing items omitted from the list "
            "are removed. Order in array determines final display order."
        ),
    )
    benefits_image_ref = serializers.JSONField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="Cloudinary ref: {'public_id': '...'} or string, or null to clear",
    )
    recommended_image_ref = serializers.JSONField(
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
    recommended_points_remove_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )
    faqs_remove_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = Treatment
        fields = "__all__"

    def validate(self, attrs):
        category = attrs.get(
            "category",
            self.instance.category_id if self.instance else None,
        )
        slug = attrs.get("slug", self.instance.slug if self.instance else None)
        title = attrs.get("title", self.instance.title if self.instance else None)
        validate_item_uniqueness(
            model=Treatment,
            category=category,
            slug=slug,
            title=title,
            exclude_pk=self.instance.pk if self.instance else None,
            cross_model=Combo,
            error_cls=serializers.ValidationError,
        )
        zone_configs = attrs.get("zone_configs")
        is_active = attrs.get(
            "is_active",
            self.instance.is_active if self.instance else True,
        )
        requires_zones = attrs.get(
            "requires_zones",
            self.instance.requires_zones if self.instance else False,
        )
        has_zones = (
            bool(zone_configs)
            if zone_configs is not None
            else bool(self.instance and self.instance.zone_configs.exists())
        )
        validate_treatment_rules(
            is_active=is_active,
            requires_zones=requires_zones,
            has_zones=has_zones,
            error_cls=serializers.ValidationError,
        )
        return attrs

    def get_cover_media(self, obj):
        first_media = obj.media.first()
        if first_media:
            return build_media_url(first_media.media, first_media.media_type)
        return None

    def get_effective_price(self, obj):
        return effective_price_for_treatment(obj)

    def get_kind(self, obj):
        return "treatment"

    def get_duration(self, obj):
        avg_duration = getattr(obj, "avg_duration", None)
        if avg_duration is None:
            avg_duration = obj.zone_configs.aggregate(avg=Avg("duration")).get("avg")
        if avg_duration is None:
            return None
        return int(round(avg_duration))

    def _parse_zone_configs(self, raw):
        if raw is None:
            return None
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception as exc:
                raise ValidationError({"zone_configs": f"JSON inválido: {exc}"})
        return raw

    def to_internal_value(self, data):
        mutable = data.copy() if hasattr(data, "copy") else dict(data)

        # Parse JSON string fields if needed (for form-data compatibility during transition)
        if "zone_configs" in mutable:
            mutable["zone_configs"] = self._parse_zone_configs(
                mutable.get("zone_configs")
            )
        if "benefits" in mutable:
            mutable["benefits"] = parse_json_list(
                mutable.get("benefits"), "benefits", ValidationError
            )
        if "recommended_points" in mutable:
            mutable["recommended_points"] = parse_json_list(
                mutable.get("recommended_points"),
                "recommended_points",
                ValidationError,
            )
        if "faqs" in mutable:
            mutable["faqs"] = parse_json_list(
                mutable.get("faqs"), "faqs", ValidationError
            )
        if "benefits_remove_ids" in mutable:
            mutable["benefits_remove_ids"] = self._parse_id_list(
                mutable.get("benefits_remove_ids"), "benefits_remove_ids"
            )
        if "recommended_points_remove_ids" in mutable:
            mutable["recommended_points_remove_ids"] = self._parse_id_list(
                mutable.get("recommended_points_remove_ids"),
                "recommended_points_remove_ids",
            )
        if "faqs_remove_ids" in mutable:
            mutable["faqs_remove_ids"] = self._parse_id_list(
                mutable.get("faqs_remove_ids"), "faqs_remove_ids"
            )
        if "media_items" in mutable:
            mutable["media_items"] = parse_json_list(
                mutable.get("media_items"), "media_items", ValidationError
            )

        return super().to_internal_value(mutable)

    def _apply_media_items(self, treatment, media_items):
        """
        Process media_items list with Cloudinary references.

        Supports:
        - {"id": "uuid"} - Keep existing media at this position
        - {"id": "uuid", "remove": true} - Delete existing media
        - {"public_id": "...", "resource_type": "image|video"} - Add new media
        - {"public_id": "...", "resource_type": "...", "alt_text": "..."} - With alt text
        """
        self._process_media_list(
            media_items=media_items,
            parent=treatment,
            media_model=TreatmentMedia,
            parent_field="treatment",
            allowed_prefixes=CATALOG_MEDIA_PREFIXES,
        )

    def _save_zone_configs(self, treatment, zone_configs):
        normalized = [
            {**cfg, "zone": getattr(cfg.get("zone"), "id", cfg.get("zone"))}
            for cfg in zone_configs
        ]
        ser = TreatmentZoneConfigSerializer(
            data=normalized, many=True, context=self.context
        )
        ser.is_valid(raise_exception=True)
        ser.save(treatment=treatment)

    def _sync_zone_configs(self, treatment, zone_configs):
        if zone_configs is None:
            return
        if not isinstance(zone_configs, (list, tuple)):
            raise ValidationError({"zone_configs": "Debe ser una lista"})

        normalized = [
            {**cfg, "zone": getattr(cfg.get("zone"), "id", cfg.get("zone"))}
            for cfg in zone_configs
        ]
        existing = list(treatment.zone_configs.all())
        existing_by_id = {str(obj.id): obj for obj in existing}
        existing_by_zone = {str(obj.zone_id): obj for obj in existing}
        seen_ids = set()
        seen_zones = set()

        for cfg in normalized:
            if not isinstance(cfg, dict):
                raise ValidationError(
                    {"zone_configs": "Cada elemento debe ser un objeto"}
                )

            item_id = cfg.get("id")
            zone_id = cfg.get("zone")
            zone_key = str(zone_id) if zone_id else None

            if zone_key:
                if zone_key in seen_zones:
                    raise ValidationError(
                        {"zone_configs": "Hay zonas duplicadas en la lista."}
                    )
                seen_zones.add(zone_key)

            payload = dict(cfg)
            payload.pop("id", None)

            if item_id:
                item_key = str(item_id)
                if item_key in seen_ids:
                    raise ValidationError(
                        {"zone_configs": "Hay IDs duplicados en la lista."}
                    )
                obj = existing_by_id.get(item_key)
                if not obj:
                    raise ValidationError(
                        {
                            "zone_configs": f"El id {item_id} no pertenece a este tratamiento"
                        }
                    )
                ser = TreatmentZoneConfigSerializer(
                    instance=obj, data=payload, context=self.context
                )
                ser.is_valid(raise_exception=True)
                ser.save()
                seen_ids.add(item_key)
                continue

            if zone_key:
                obj = existing_by_zone.get(zone_key)
                if obj:
                    ser = TreatmentZoneConfigSerializer(
                        instance=obj, data=payload, context=self.context
                    )
                    ser.is_valid(raise_exception=True)
                    ser.save()
                    seen_ids.add(str(obj.id))
                    continue

            ser = TreatmentZoneConfigSerializer(data=payload, context=self.context)
            ser.is_valid(raise_exception=True)
            ser.save(treatment=treatment)

        existing_ids = {str(obj.id) for obj in existing}
        to_delete = existing_ids - seen_ids
        if to_delete:
            treatment.zone_configs.filter(id__in=to_delete).delete()

    def create(self, validated_data):
        tags = validated_data.pop("tags", None)
        benefits = validated_data.pop("benefits", [])
        recommended_points = validated_data.pop("recommended_points", [])
        faqs = validated_data.pop("faqs", [])
        benefits_remove_ids = validated_data.pop("benefits_remove_ids", None)
        recommended_points_remove_ids = validated_data.pop(
            "recommended_points_remove_ids", None
        )
        faqs_remove_ids = validated_data.pop("faqs_remove_ids", None)
        zone_configs = validated_data.pop("zone_configs", [])
        media_items = validated_data.pop("media_items", None)

        benefits_image_ref = self._pop_optional_input(
            validated_data, "benefits_image_ref"
        )
        recommended_image_ref = self._pop_optional_input(
            validated_data, "recommended_image_ref"
        )

        with transaction.atomic():
            treatment = super().create(validated_data)

            if tags is not None:
                treatment.tags.set(tags)

            # Apply image references
            image_update_fields = []
            if self._apply_image_input(
                    treatment,
                    "benefits_image",
                    benefits_image_ref,
                    CATALOG_IMAGE_PREFIXES,
                ):
                image_update_fields.append("benefits_image")
            if self._apply_image_input(
                    treatment,
                    "recommended_image",
                    recommended_image_ref,
                    CATALOG_IMAGE_PREFIXES,
                ):
                image_update_fields.append("recommended_image")
            if image_update_fields:
                treatment.save(update_fields=image_update_fields)

            self._apply_generic_changes(
                treatment,
                ItemBenefit,
                benefits,
                [],
                "benefits",
                ["title", "detail", "order"],
                True,
            )
            self._apply_generic_changes(
                treatment,
                ItemRecommendedPoint,
                recommended_points,
                [],
                "recommended_points",
                ["title", "detail", "order"],
                True,
            )
            self._apply_generic_changes(
                treatment,
                ItemFAQ,
                faqs,
                faqs_remove_ids,
                "faqs",
                ["question", "answer", "order"],
                True,
            )

            if media_items is not None:
                self._apply_media_items(treatment, media_items)

            if zone_configs:
                self._save_zone_configs(treatment, zone_configs)

            return treatment

    def update(self, instance, validated_data):
        was_active = instance.is_active
        tags = validated_data.pop("tags", None)
        benefits = validated_data.pop("benefits", None)
        recommended_points = validated_data.pop("recommended_points", None)
        faqs = validated_data.pop("faqs", None)
        benefits_remove_ids = validated_data.pop("benefits_remove_ids", None)
        recommended_points_remove_ids = validated_data.pop(
            "recommended_points_remove_ids", None
        )
        faqs_remove_ids = validated_data.pop("faqs_remove_ids", None)
        zone_configs = validated_data.pop("zone_configs", None)
        media_items = validated_data.pop("media_items", None)

        benefits_image_ref = self._pop_optional_input(
            validated_data, "benefits_image_ref"
        )
        recommended_image_ref = self._pop_optional_input(
            validated_data, "recommended_image_ref"
        )

        with transaction.atomic():
            treatment = super().update(instance, validated_data)

            if tags is not None:
                treatment.tags.set(tags)

            # Apply image references
            update_fields = []
            if self._apply_image_input(
                    treatment,
                    "benefits_image",
                    benefits_image_ref,
                    CATALOG_IMAGE_PREFIXES,
                ):
                update_fields.append("benefits_image")
            if self._apply_image_input(
                    treatment,
                    "recommended_image",
                    recommended_image_ref,
                    CATALOG_IMAGE_PREFIXES,
                ):
                update_fields.append("recommended_image")
            if update_fields:
                treatment.save(update_fields=update_fields)

            self._apply_generic_changes(
                treatment,
                ItemBenefit,
                benefits,
                benefits_remove_ids,
                "benefits",
                ["title", "detail", "order"],
                False,
            )
            self._apply_generic_changes(
                treatment,
                ItemRecommendedPoint,
                recommended_points,
                recommended_points_remove_ids,
                "recommended_points",
                ["title", "detail", "order"],
                False,
            )
            self._apply_generic_changes(
                treatment,
                ItemFAQ,
                faqs,
                faqs_remove_ids,
                "faqs",
                ["question", "answer", "order"],
                False,
            )

            if media_items is not None:
                self._apply_media_items(treatment, media_items)

            if zone_configs is not None:
                self._sync_zone_configs(treatment, zone_configs)

            if was_active and not treatment.is_active:
                cleanup_treatment_deactivation([treatment.id])

        return treatment


class PublicTreatmentSerializer(TreatmentSerializer):
    category = serializers.SerializerMethodField()
    journey = serializers.SerializerMethodField()
    zone_configs = serializers.SerializerMethodField()
    techniques = TechniqueSerializer(many=True, read_only=True)
    objectives = ObjectiveSerializer(many=True, read_only=True)
    intensities = IntensitySerializer(many=True, read_only=True)

    class Meta:
        model = Treatment
        fields = [
            "id",
            "slug",
            "title",
            "description",
            "short_description",
            "seo_title",
            "seo_description",
            "recommended_description",
            "benefits_image",
            "recommended_image",
            "category",
            "journey",
            "tags",
            "techniques",
            "objectives",
            "intensities",
            "requires_zones",
            "zone_configs",
            "media",
            "benefits",
            "recommended_points",
            "faqs",
            "cover_media",
            "effective_price",
            "kind",
            "duration",
        ]

    def get_category(self, obj):
        category = getattr(obj, "category", None)
        if not category:
            return None
        return {"id": category.id, "name": category.name, "slug": category.slug}

    def get_journey(self, obj):
        journey = getattr(obj, "journey", None)
        if not journey:
            return None
        return {"id": journey.id, "title": journey.title, "slug": journey.slug}

    def get_zone_configs(self, obj):
        return PublicTreatmentZoneConfigSerializer(
            obj.zone_configs.all(), many=True, context=self.context
        ).data


class PublicTreatmentZoneConfigSerializer(UUIDSerializer):
    zone_name = serializers.SerializerMethodField()

    class Meta:
        model = TreatmentZoneConfig
        fields = [
            "id",
            "treatment",
            "zone",
            "zone_name",
            "duration",
            "price",
            "promotional_price",
        ]

    def get_zone_name(self, obj):
        zone = getattr(obj, "zone", None)
        if not zone:
            return None
        return zone.name
