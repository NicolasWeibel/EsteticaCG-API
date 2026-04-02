"""
Journey serializers with JSON-only Cloudinary media support.

This module has been migrated to accept only JSON requests with Cloudinary
asset references instead of multipart file uploads.
"""

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ..models import (
    Journey,
    JourneyMedia,
    ItemBenefit,
    ItemRecommendedPoint,
    ItemFAQ,
)
from ..services.pricing import effective_price_for_journey
from ..services.uniqueness import validate_item_uniqueness
from ..services.cloudinary_assets import CATALOG_MEDIA_PREFIXES, CATALOG_IMAGE_PREFIXES
from .base import UUIDSerializer
from .gallery import JourneyMediaSerializer
from .item_content import (
    ItemBenefitSerializer,
    ItemRecommendedPointSerializer,
    ItemFAQSerializer,
)
from .item_content_sync import GenericItemContentSyncMixin
from .cloudinary_mixin import CloudinaryMediaMixin
from .utils import parse_json_list
from ..utils.media import build_media_url


class JourneySerializer(
    GenericItemContentSyncMixin, CloudinaryMediaMixin, UUIDSerializer
):
    """
    Journey serializer with JSON-only Cloudinary media support.

    Media handling:
    - Use `media_items` to manage gallery (create, reorder, delete)
    - Use `benefits_image_ref` and `recommended_image_ref` for single images
    - All media references must be Cloudinary public_ids from signed uploads
    """

    media = JourneyMediaSerializer(many=True, read_only=True)
    benefits = ItemBenefitSerializer(many=True, required=False)
    recommended_points = ItemRecommendedPointSerializer(many=True, required=False)
    faqs = ItemFAQSerializer(many=True, required=False)
    cover_media = serializers.SerializerMethodField()
    effective_price = serializers.SerializerMethodField()
    kind = serializers.SerializerMethodField()

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
        model = Journey
        fields = "__all__"

    def validate(self, attrs):
        category = attrs.get(
            "category",
            self.instance.category_id if self.instance else None,
        )
        slug = attrs.get("slug", self.instance.slug if self.instance else None)
        title = attrs.get("title", self.instance.title if self.instance else None)
        validate_item_uniqueness(
            model=Journey,
            category=category,
            slug=slug,
            title=title,
            exclude_pk=self.instance.pk if self.instance else None,
            error_cls=serializers.ValidationError,
        )
        return attrs

    def get_cover_media(self, obj):
        first_media = obj.media.first()
        if first_media:
            return build_media_url(first_media.media, first_media.media_type)
        return None

    def get_effective_price(self, obj):
        return effective_price_for_journey(obj)

    def get_kind(self, obj):
        return "journey"

    def _apply_media_items(self, journey, media_items):
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
            parent=journey,
            media_model=JourneyMedia,
            parent_field="journey",
            allowed_prefixes=CATALOG_MEDIA_PREFIXES,
        )

    def to_internal_value(self, data):
        mutable = data.copy() if hasattr(data, "copy") else dict(data)

        # Parse JSON string fields if needed (for form-data compatibility during transition)
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

    def create(self, validated_data):
        benefits = validated_data.pop("benefits", [])
        recommended_points = validated_data.pop("recommended_points", [])
        faqs = validated_data.pop("faqs", [])
        validated_data.pop("benefits_remove_ids", None)
        validated_data.pop("recommended_points_remove_ids", None)
        validated_data.pop("faqs_remove_ids", None)
        media_items = validated_data.pop("media_items", None)

        # Extract image refs before create
        benefits_image_ref = self._pop_optional_input(
            validated_data, "benefits_image_ref"
        )
        recommended_image_ref = self._pop_optional_input(
            validated_data, "recommended_image_ref"
        )

        with transaction.atomic():
            journey = super().create(validated_data)

            # Apply image references
            image_update_fields = []
            if self._apply_image_input(
                    journey,
                    "benefits_image",
                    benefits_image_ref,
                    CATALOG_IMAGE_PREFIXES,
                ):
                image_update_fields.append("benefits_image")
            if self._apply_image_input(
                    journey,
                    "recommended_image",
                    recommended_image_ref,
                    CATALOG_IMAGE_PREFIXES,
                ):
                image_update_fields.append("recommended_image")
            if image_update_fields:
                journey.save(update_fields=image_update_fields)

            self._apply_generic_changes(
                journey,
                ItemBenefit,
                benefits,
                [],
                "benefits",
                ["title", "detail", "order"],
                True,
            )
            self._apply_generic_changes(
                journey,
                ItemRecommendedPoint,
                recommended_points,
                [],
                "recommended_points",
                ["title", "detail", "order"],
                True,
            )
            self._apply_generic_changes(
                journey,
                ItemFAQ,
                faqs,
                [],
                "faqs",
                ["question", "answer", "order"],
                True,
            )

            if media_items is not None:
                self._apply_media_items(journey, media_items)

            return journey

    def update(self, instance, validated_data):
        benefits = validated_data.pop("benefits", None)
        recommended_points = validated_data.pop("recommended_points", None)
        faqs = validated_data.pop("faqs", None)
        benefits_remove_ids = validated_data.pop("benefits_remove_ids", None)
        recommended_points_remove_ids = validated_data.pop(
            "recommended_points_remove_ids", None
        )
        faqs_remove_ids = validated_data.pop("faqs_remove_ids", None)
        media_items = validated_data.pop("media_items", None)

        # Extract image refs
        benefits_image_ref = self._pop_optional_input(
            validated_data, "benefits_image_ref"
        )
        recommended_image_ref = self._pop_optional_input(
            validated_data, "recommended_image_ref"
        )

        with transaction.atomic():
            journey = super().update(instance, validated_data)

            # Apply image references
            update_fields = []
            if self._apply_image_input(
                    journey,
                    "benefits_image",
                    benefits_image_ref,
                    CATALOG_IMAGE_PREFIXES,
                ):
                update_fields.append("benefits_image")
            if self._apply_image_input(
                    journey,
                    "recommended_image",
                    recommended_image_ref,
                    CATALOG_IMAGE_PREFIXES,
                ):
                update_fields.append("recommended_image")
            if update_fields:
                journey.save(update_fields=update_fields)

            self._apply_generic_changes(
                journey,
                ItemBenefit,
                benefits,
                benefits_remove_ids,
                "benefits",
                ["title", "detail", "order"],
                False,
            )
            self._apply_generic_changes(
                journey,
                ItemRecommendedPoint,
                recommended_points,
                recommended_points_remove_ids,
                "recommended_points",
                ["title", "detail", "order"],
                False,
            )
            self._apply_generic_changes(
                journey,
                ItemFAQ,
                faqs,
                faqs_remove_ids,
                "faqs",
                ["question", "answer", "order"],
                False,
            )

            if media_items is not None:
                self._apply_media_items(journey, media_items)

        return journey


class PublicJourneySerializer(JourneySerializer):
    category = serializers.SerializerMethodField()

    class Meta:
        model = Journey
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
            "default_sort",
            "addons",
            "media",
            "benefits",
            "recommended_points",
            "faqs",
            "cover_media",
            "effective_price",
            "kind",
        ]

    def get_category(self, obj):
        category = getattr(obj, "category", None)
        if not category:
            return None
        return {"id": category.id, "name": category.name, "slug": category.slug}
