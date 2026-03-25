import json
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ..models import (
    Combo,
    Treatment,
    ComboIngredient,
    ComboSessionItem,
    ComboMedia,
    ItemBenefit,
    ItemRecommendedPoint,
    ItemFAQ,
)
from ..services.pricing import effective_price_for_combo
from ..services.uniqueness import validate_item_uniqueness
from ..services.combo_sessions import (
    prune_session_items_for_sessions,
    serialize_session_items_for_validation,
)
from ..services.validation import (
    validate_combo_rules,
    validate_combo_treatments_active,
    validate_optional_gt_zero_or_null,
)
from ..utils.gallery import reorder_gallery
from .base import UUIDSerializer
from .gallery import ComboMediaSerializer
from .item_content import (
    ItemBenefitSerializer,
    ItemRecommendedPointSerializer,
    ItemFAQSerializer,
)
from .item_content_sync import GenericItemContentSyncMixin
from .utils import clean_uploaded_media, parse_json_list
from .media import MediaUploadMixin
from ..utils.media import build_media_url
from .fields import TagListField
from .filters import TechniqueSerializer, ObjectiveSerializer, IntensitySerializer


class ComboIngredientSerializer(UUIDSerializer):
    class Meta:
        model = ComboIngredient
        fields = "__all__"
        extra_kwargs = {"combo": {"read_only": True}}


class ComboSessionItemSerializer(UUIDSerializer):
    treatment_zone_config = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = ComboSessionItem
        fields = "__all__"
        extra_kwargs = {
            "combo": {"read_only": True},
            "ingredient": {"required": False},
        }


class ComboSerializer(GenericItemContentSyncMixin, MediaUploadMixin, UUIDSerializer):
    ingredients = ComboIngredientSerializer(many=True, required=False)
    session_items = ComboSessionItemSerializer(many=True, required=False)
    media = ComboMediaSerializer(many=True, read_only=True)
    benefits = ItemBenefitSerializer(many=True, required=False)
    recommended_points = ItemRecommendedPointSerializer(many=True, required=False)
    faqs = ItemFAQSerializer(many=True, required=False)
    tags = TagListField(required=False)
    cover_media = serializers.SerializerMethodField()
    effective_price = serializers.SerializerMethodField()
    kind = serializers.SerializerMethodField()
    uploaded_media = serializers.ListField(
        child=serializers.FileField(allow_empty_file=False, use_url=False),
        write_only=True,
        required=False,
    )
    removed_media_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )
    ordered_media_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )
    media_order = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
    )
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
        model = Combo
        fields = "__all__"

    def validate(self, attrs):
        category = attrs.get(
            "category",
            self.instance.category_id if self.instance else None,
        )
        slug = attrs.get("slug", self.instance.slug if self.instance else None)
        title = attrs.get("title", self.instance.title if self.instance else None)
        validate_item_uniqueness(
            model=Combo,
            category=category,
            slug=slug,
            title=title,
            exclude_pk=self.instance.pk if self.instance else None,
            cross_model=Treatment,
            error_cls=serializers.ValidationError,
        )
        is_active = attrs.get(
            "is_active",
            self.instance.is_active if self.instance else True,
        )
        sessions = attrs.get(
            "sessions",
            (
                self.instance.sessions
                if self.instance
                else Combo._meta.get_field("sessions").default
            ),
        )
        duration = attrs.get(
            "duration",
            self.instance.duration if self.instance else None,
        )
        session_items = attrs.get("session_items")
        validate_optional_gt_zero_or_null(
            field_name="duration",
            value=duration,
            error_cls=serializers.ValidationError,
        )
        if sessions == 0:
            validate_combo_rules(
                is_active=is_active,
                sessions=sessions,
                ingredient_ids=[],
                session_items=session_items,
                error_cls=serializers.ValidationError,
            )
        return attrs

    def _save_ingredients(self, combo, ingredients):
        # Normaliza FK para aceptar UUID o objeto en el payload
        normalized = [
            {
                **ing,
                "treatment_zone_config": getattr(
                    ing.get("treatment_zone_config"),
                    "id",
                    ing.get("treatment_zone_config"),
                ),
            }
            for ing in ingredients
        ]
        ser = ComboIngredientSerializer(
            data=normalized, many=True, context=self.context
        )
        ser.is_valid(raise_exception=True)
        ser.save(combo=combo)

    def _get_tzc_id_from_payload(self, ingredient_payload):
        tzc_value = ingredient_payload.get("treatment_zone_config")
        tzc_id = getattr(tzc_value, "id", tzc_value)
        if not tzc_id:
            raise ValidationError(
                {
                    "ingredients": (
                        "Cada ingrediente debe incluir treatment_zone_config."
                    )
                }
            )
        return tzc_id

    def _sync_ingredients(self, combo, ingredients_payload):
        if ingredients_payload is None:
            return

        def _invalidate_ingredients_prefetch():
            if getattr(combo, "_prefetched_objects_cache", None):
                combo._prefetched_objects_cache.pop("ingredients", None)

        target_tzc_ids = []
        seen_tzc_ids = set()
        for ingredient_payload in ingredients_payload:
            if not isinstance(ingredient_payload, dict):
                raise ValidationError(
                    {"ingredients": "Cada ingrediente debe ser un objeto."}
                )
            tzc_id = self._get_tzc_id_from_payload(ingredient_payload)
            tzc_key = str(tzc_id)
            if tzc_key in seen_tzc_ids:
                raise ValidationError(
                    {"ingredients": ("No se permiten treatment_zone_config repetidos.")}
                )
            seen_tzc_ids.add(tzc_key)
            target_tzc_ids.append(tzc_id)

        if not target_tzc_ids:
            combo.ingredients.all().delete()
            _invalidate_ingredients_prefetch()
            return

        current_tzc_ids = list(
            combo.ingredients.values_list("treatment_zone_config_id", flat=True)
        )
        current_tzc_keys = {str(tzc_id) for tzc_id in current_tzc_ids}
        target_tzc_keys = {str(tzc_id) for tzc_id in target_tzc_ids}

        to_add = [
            {"treatment_zone_config": tzc_id}
            for tzc_id in target_tzc_ids
            if str(tzc_id) not in current_tzc_keys
        ]
        to_remove = [
            tzc_id for tzc_id in current_tzc_ids if str(tzc_id) not in target_tzc_keys
        ]

        if to_add:
            self._save_ingredients(combo, to_add)
        if to_remove:
            combo.ingredients.filter(treatment_zone_config_id__in=to_remove).delete()
        if to_add or to_remove:
            _invalidate_ingredients_prefetch()

    def _normalize_combo_without_ingredients(self, combo):
        if combo.ingredients.exists():
            return

        combo.session_items.all().delete()

        update_fields = []
        if combo.is_active:
            combo.is_active = False
            update_fields.append("is_active")
        if combo.sessions != 0:
            combo.sessions = 0
            update_fields.append("sessions")
        if update_fields:
            combo.save(update_fields=update_fields)

    def _save_session_items(self, combo, session_items):
        normalized = self._normalize_session_items(combo, session_items)
        ser = ComboSessionItemSerializer(
            data=normalized, many=True, context=self.context
        )
        ser.is_valid(raise_exception=True)
        ser.save(combo=combo)

    def _create_media(self, combo, media):
        start = combo.media.count()
        to_create = []
        for index, media_file in enumerate(media, start=start):
            media_type = self._media_type_for_file(media_file)
            to_create.append(
                ComboMedia(
                    combo=combo,
                    media=media_file,
                    media_type=media_type,
                    order=index,
                )
            )
        if to_create:
            ComboMedia.objects.bulk_create(to_create)

    def _normalize_session_items(self, combo, items):
        if items is None:
            return None
        if not isinstance(items, (list, tuple)):
            raise ValidationError({"session_items": "Debe ser una lista"})

        ingredient_map = {str(obj.id): obj for obj in combo.ingredients.all()}
        tzc_map = {
            str(obj.treatment_zone_config_id): obj for obj in combo.ingredients.all()
        }

        normalized = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValidationError(
                    {"session_items": "Cada item debe ser un objeto."}
                )
            session_index = item.get("session_index")
            ingredient_id = item.get("ingredient")
            tzc_id = item.get("treatment_zone_config")

            if session_index is None:
                raise ValidationError(
                    {"session_items": "Cada item requiere session_index."}
                )
            if ingredient_id and tzc_id:
                raise ValidationError(
                    {
                        "session_items": (
                            "Cada item debe tener 'ingredient' o "
                            "'treatment_zone_config', pero no ambos."
                        )
                    }
                )
            if not ingredient_id and not tzc_id:
                raise ValidationError(
                    {
                        "session_items": (
                            "Cada item debe incluir 'ingredient' o "
                            "'treatment_zone_config'."
                        )
                    }
                )

            try:
                session_index = int(session_index)
            except (TypeError, ValueError):
                raise ValidationError(
                    {"session_items": ("session_index debe ser un número válido.")}
                )

            ingredient = None
            if ingredient_id:
                ingredient = ingredient_map.get(str(ingredient_id))
            if ingredient is None and tzc_id:
                ingredient = tzc_map.get(str(tzc_id))
            if not ingredient:
                raise ValidationError(
                    {"session_items": ("El ingrediente no pertenece al combo.")}
                )

            normalized.append(
                {
                    "session_index": session_index,
                    "ingredient": ingredient.id,
                }
            )
        return normalized

    def _validate_session_items(self, combo, items):
        ingredient_ids = combo.ingredients.values_list("id", flat=True)
        validate_combo_rules(
            is_active=combo.is_active,
            sessions=combo.sessions or 0,
            ingredient_ids=ingredient_ids,
            session_items=items,
            error_cls=ValidationError,
        )

    def _validate_ingredient_treatments_active(self, combo):
        tzc_ids = combo.ingredients.values_list("treatment_zone_config_id", flat=True)
        validate_combo_treatments_active(
            is_active=combo.is_active,
            treatment_zone_config_ids=tzc_ids,
            error_cls=ValidationError,
        )

    def to_internal_value(self, data):
        mutable = data.copy()
        media_order = mutable.get("media_order")
        if "session_items" in mutable:
            mutable["session_items"] = parse_json_list(
                mutable.get("session_items"), "session_items", ValidationError
            )
        if "ingredients" in mutable:
            parsed_ing = self._parse_ingredients(mutable.get("ingredients"))
            if hasattr(mutable, "setlist") and isinstance(parsed_ing, list):
                mutable.setlist("ingredients", parsed_ing)
            else:
                mutable["ingredients"] = parsed_ing
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
        if "uploaded_media" in mutable:
            cleaned = clean_uploaded_media(mutable.get("uploaded_media"))
            if cleaned is None:
                mutable.pop("uploaded_media", None)
            else:
                if hasattr(mutable, "setlist"):
                    mutable.setlist("uploaded_media", cleaned)
                else:
                    mutable["uploaded_media"] = cleaned
        if media_order is not None:
            parsed_order = self._parse_media_order(media_order)
            self.context["media_order"] = parsed_order
            files_map, plain_list = self._extract_uploaded_map(data)
            self.context["uploaded_map"] = files_map
            self.context["uploaded_list"] = plain_list
            if hasattr(mutable, "setlist"):
                mutable.setlist("media_order", parsed_order)
            else:
                mutable["media_order"] = parsed_order
        return super().to_internal_value(mutable)

    def _parse_media_order(self, raw):
        if raw is None:
            return None
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception as exc:
                raise ValidationError({"media_order": f"JSON inválido: {exc}"})
        if not isinstance(raw, (list, tuple)):
            raise ValidationError({"media_order": "Debe ser una lista"})
        normalized = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValidationError(
                    {
                        "media_order": "Cada elemento debe ser un objeto con id o upload_key"
                    }
                )
            img_id = item.get("id")
            upload_key = item.get("upload_key")
            if not img_id and not upload_key:
                raise ValidationError(
                    {"media_order": "Cada elemento debe tener 'id' o 'upload_key'"}
                )
            normalized.append(
                {
                    "id": str(img_id) if img_id else None,
                    "upload_key": str(upload_key) if upload_key else None,
                }
            )
        return normalized

    def _parse_ingredients(self, raw):
        if raw is None:
            return None
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception as exc:
                raise ValidationError({"ingredients": f"JSON inválido: {exc}"})
        if hasattr(raw, "read"):
            try:
                content = raw.read()
                if hasattr(raw, "seek"):
                    raw.seek(0)
                return json.loads(content)
            except Exception as exc:
                raise ValidationError({"ingredients": f"JSON inválido: {exc}"})
        return raw

    def _extract_uploaded_map(self, data):
        request = self.context.get("request")
        files_map = {}
        if request and hasattr(request, "FILES"):
            for key in request.FILES:
                if key.startswith("uploaded_media[") and key.endswith("]"):
                    upload_key = key[len("uploaded_media[") : -1]
                    files_map[upload_key] = request.FILES.get(key)
        plain_list = []
        if request and hasattr(request, "FILES"):
            plain_list = request.FILES.getlist("uploaded_media")
        return files_map, plain_list

    def _apply_mixed_order(self, combo, media_order, uploaded_map, uploaded_list):
        existing_qs = list(combo.media.all())
        existing_map = {str(item.id): item for item in existing_qs}
        used_ids = set()
        new_objs = []
        final_existing = []
        plain_iter = iter(uploaded_list or [])

        for idx, item in enumerate(media_order):
            media_id = item.get("id")
            upload_key = item.get("upload_key")
            if media_id:
                media_obj = existing_map.get(str(media_id))
                if not media_obj:
                    raise ValidationError(
                        {"media_order": f"Media {media_id} no pertenece al combo"}
                    )
                used_ids.add(str(media_id))
                media_obj.order = idx
                final_existing.append(media_obj)
            elif upload_key:
                file = uploaded_map.get(upload_key)
                if not file:
                    try:
                        file = next(plain_iter)
                    except StopIteration:
                        raise ValidationError(
                            {
                                "media_order": f"No se encontró archivo para upload_key '{upload_key}'"
                            }
                        )
                media_type = self._media_type_for_file(file)
                new_objs.append(
                    ComboMedia(
                        combo=combo,
                        media=file,
                        media_type=media_type,
                        order=idx,
                    )
                )

        tail = [item for item in existing_qs if str(item.id) not in used_ids]
        order_start = len(media_order)
        for offset, media_obj in enumerate(tail):
            media_obj.order = order_start + offset
            final_existing.append(media_obj)

        if new_objs:
            ComboMedia.objects.bulk_create(new_objs)
        if final_existing:
            ComboMedia.objects.bulk_update(final_existing, ["order"])

    def get_cover_media(self, obj):
        first_media = obj.media.first()
        if first_media:
            return build_media_url(first_media.media, first_media.media_type)
        return None

    def get_effective_price(self, obj):
        return effective_price_for_combo(obj)

    def get_kind(self, obj):
        return "combo"

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
        ingredients = validated_data.pop("ingredients", [])
        session_items = validated_data.pop("session_items", None)
        uploaded_media = validated_data.pop("uploaded_media", [])
        removed_ids = validated_data.pop("removed_media_ids", [])
        ordered_media_ids = validated_data.pop("ordered_media_ids", [])
        media_order = validated_data.pop("media_order", None)
        uploaded_map = self.context.get("uploaded_map", {})
        uploaded_list = self.context.get("uploaded_list", [])
        with transaction.atomic():
            combo = super().create(validated_data)
            if tags is not None:
                combo.tags.set(tags)
            self._apply_generic_changes(
                combo,
                ItemBenefit,
                benefits,
                [],
                "benefits",
                ["title", "detail", "order"],
                True,
            )
            self._apply_generic_changes(
                combo,
                ItemRecommendedPoint,
                recommended_points,
                [],
                "recommended_points",
                ["title", "detail", "order"],
                True,
            )
            self._apply_generic_changes(
                combo,
                ItemFAQ,
                faqs,
                faqs_remove_ids,
                "faqs",
                ["question", "answer", "order"],
                True,
            )
            if removed_ids:
                combo.media.filter(id__in=removed_ids).delete()
            if media_order is not None:
                self._apply_mixed_order(combo, media_order, uploaded_map, uploaded_list)
            elif uploaded_media:
                self._create_media(combo, uploaded_media)
            if ingredients:
                self._save_ingredients(combo, ingredients)
            self._validate_ingredient_treatments_active(combo)
            if session_items is None:
                self._validate_session_items(combo, None)
                return combo
            normalized_session_items = self._normalize_session_items(
                combo, session_items
            )
            self._validate_session_items(combo, normalized_session_items)
            combo.session_items.all().delete()
            if normalized_session_items:
                self._save_session_items(combo, normalized_session_items)
            return combo

    def update(self, instance, validated_data):
        ingredients_provided = "ingredients" in self.initial_data
        tags = validated_data.pop("tags", None)
        benefits = validated_data.pop("benefits", None)
        recommended_points = validated_data.pop("recommended_points", None)
        faqs = validated_data.pop("faqs", None)
        benefits_remove_ids = validated_data.pop("benefits_remove_ids", None)
        recommended_points_remove_ids = validated_data.pop(
            "recommended_points_remove_ids", None
        )
        faqs_remove_ids = validated_data.pop("faqs_remove_ids", None)
        ingredients = validated_data.pop("ingredients", None)
        if not ingredients_provided:
            ingredients = [] if not self.partial else None
        session_items = validated_data.pop("session_items", None)
        uploaded_media = validated_data.pop("uploaded_media", [])
        removed_ids = validated_data.pop("removed_media_ids", [])
        ordered_media_ids = validated_data.pop("ordered_media_ids", [])
        media_order = validated_data.pop("media_order", None)
        uploaded_map = self.context.get("uploaded_map", {})
        uploaded_list = self.context.get("uploaded_list", [])
        with transaction.atomic():
            combo = super().update(instance, validated_data)
            if tags is not None:
                combo.tags.set(tags)
            self._apply_generic_changes(
                combo,
                ItemBenefit,
                benefits,
                benefits_remove_ids,
                "benefits",
                ["title", "detail", "order"],
                False,
            )
            self._apply_generic_changes(
                combo,
                ItemRecommendedPoint,
                recommended_points,
                recommended_points_remove_ids,
                "recommended_points",
                ["title", "detail", "order"],
                False,
            )
            self._apply_generic_changes(
                combo,
                ItemFAQ,
                faqs,
                faqs_remove_ids,
                "faqs",
                ["question", "answer", "order"],
                False,
            )
            if removed_ids:
                combo.media.filter(id__in=removed_ids).delete()
            if media_order is not None:
                self._apply_mixed_order(combo, media_order, uploaded_map, uploaded_list)
            if uploaded_media:
                self._create_media(combo, uploaded_media)
            if ingredients is not None:
                self._sync_ingredients(instance, ingredients)
                self._normalize_combo_without_ingredients(instance)
            self._validate_ingredient_treatments_active(instance)
            if session_items is not None:
                normalized_session_items = self._normalize_session_items(
                    instance, session_items
                )
                self._validate_session_items(instance, normalized_session_items)
                instance.session_items.all().delete()
                if normalized_session_items:
                    self._save_session_items(instance, normalized_session_items)
            else:
                prune_session_items_for_sessions(instance, instance.sessions)
                existing_items = serialize_session_items_for_validation(
                    ComboSessionItem.objects.filter(combo_id=instance.id)
                )
                self._validate_session_items(instance, existing_items)
            if ordered_media_ids:
                reorder_gallery(combo, ordered_media_ids)
            return combo


class PublicComboSerializer(ComboSerializer):
    category = serializers.SerializerMethodField()
    journey = serializers.SerializerMethodField()
    ingredients = serializers.SerializerMethodField()
    zones = serializers.SerializerMethodField()
    techniques = TechniqueSerializer(many=True, read_only=True)
    objectives = ObjectiveSerializer(many=True, read_only=True)
    intensities = IntensitySerializer(many=True, read_only=True)

    class Meta:
        model = Combo
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
            "price",
            "promotional_price",
            "sessions",
            "session_freq",
            "session_interval",
            "occurrences_per_period",
            "min_session_interval_days",
            "duration",
            "ingredients",
            "zones",
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

    def get_journey(self, obj):
        journey = getattr(obj, "journey", None)
        if not journey:
            return None
        return {"id": journey.id, "title": journey.title, "slug": journey.slug}

    def get_ingredients(self, obj):
        items = obj.session_items.all()
        treatment_sessions = {}
        treatment_names = {}
        for item in items:
            ingredient = getattr(item, "ingredient", None)
            if not ingredient:
                continue
            tzc = getattr(ingredient, "treatment_zone_config", None)
            if not tzc:
                continue
            treatment = getattr(tzc, "treatment", None)
            if not treatment:
                continue
            tid = str(treatment.id)
            treatment_names[tid] = treatment.title
            treatment_sessions.setdefault(tid, set()).add(item.session_index)

        summary = []
        for tid, sessions in treatment_sessions.items():
            summary.append(
                {
                    "treatment_id": tid,
                    "treatment_name": treatment_names.get(tid),
                    "session_count": len(sessions),
                }
            )
        return summary

    def get_zones(self, obj):
        zones_map = {}
        for ingredient in obj.ingredients.all():
            tzc = getattr(ingredient, "treatment_zone_config", None)
            if not tzc:
                continue
            zone = getattr(tzc, "zone", None)
            if not zone:
                continue
            zid = str(zone.id)
            if zid not in zones_map:
                zones_map[zid] = {"id": zone.id, "name": zone.name}
        return list(zones_map.values())
