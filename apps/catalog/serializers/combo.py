import json
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ..models import (
    Combo,
    Treatment,
    ComboIngredient,
    ComboSessionItem,
    ComboImage,
    ItemBenefit,
    ItemRecommendedPoint,
    ItemFAQ,
)
from ..services.pricing import effective_price_for_combo
from ..utils.gallery import reorder_gallery
from .base import UUIDSerializer
from .gallery import ComboImageSerializer
from .item_content import (
    ItemBenefitSerializer,
    ItemRecommendedPointSerializer,
    ItemFAQSerializer,
)
from .fields import TagListField


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
        }


class ComboSerializer(UUIDSerializer):
    ingredients = ComboIngredientSerializer(many=True, required=False)
    session_items = ComboSessionItemSerializer(many=True, required=False)
    images = ComboImageSerializer(many=True, read_only=True)
    benefits = ItemBenefitSerializer(many=True, required=False)
    recommended_points = ItemRecommendedPointSerializer(many=True, required=False)
    faqs = ItemFAQSerializer(many=True, required=False)
    tags = TagListField(required=False)
    cover_image = serializers.SerializerMethodField()
    effective_price = serializers.SerializerMethodField()
    kind = serializers.SerializerMethodField()
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False, use_url=False),
        write_only=True,
        required=False,
    )
    removed_image_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )
    ordered_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )
    images_order = serializers.ListField(
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
        if not self.instance or "slug" in attrs:
            slug = attrs.get("slug")
            if not slug and self.instance:
                slug = self.instance.slug
            if slug and Treatment.objects.filter(slug=slug).exists():
                raise serializers.ValidationError(
                    {"slug": "El slug ya está en uso por un tratamiento."}
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

    def _save_session_items(self, combo, session_items):
        normalized = self._normalize_session_items(combo, session_items)
        ser = ComboSessionItemSerializer(
            data=normalized, many=True, context=self.context
        )
        ser.is_valid(raise_exception=True)
        ser.save(combo=combo)

    def _create_images(self, combo, images):
        start = combo.images.count()
        to_create = []
        for index, img_file in enumerate(images, start=start):
            to_create.append(ComboImage(combo=combo, image=img_file, order=index))
        if to_create:
            ComboImage.objects.bulk_create(to_create)

    def _clean_uploaded_images(self, raw):
        if raw is None:
            return None
        if hasattr(raw, "read"):
            return [raw]
        if isinstance(raw, str):
            return []
        if isinstance(raw, (list, tuple)):
            return [item for item in raw if hasattr(item, "read")]
        return []

    def _parse_json_list(self, raw, field_name):
        if raw is None:
            return None
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception as exc:
                raise ValidationError({field_name: f"JSON inválido: {exc}"})
        if hasattr(raw, "read"):
            try:
                content = raw.read()
                if hasattr(raw, "seek"):
                    raw.seek(0)
                return json.loads(content)
            except Exception as exc:
                raise ValidationError({field_name: f"JSON inválido: {exc}"})
        return raw

    def _normalize_session_items(self, combo, items):
        if items is None:
            return None
        if not isinstance(items, (list, tuple)):
            raise ValidationError({"session_items": "Debe ser una lista"})

        ingredient_map = {str(obj.id): obj for obj in combo.ingredients.all()}
        tzc_map = {
            str(obj.treatment_zone_config_id): obj
            for obj in combo.ingredients.all()
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
                    {
                        "session_items": (
                            "session_index debe ser un número válido."
                        )
                    }
                )

            ingredient = None
            if ingredient_id:
                ingredient = ingredient_map.get(str(ingredient_id))
            if ingredient is None and tzc_id:
                ingredient = tzc_map.get(str(tzc_id))
            if not ingredient:
                raise ValidationError(
                    {
                        "session_items": (
                            "El ingrediente no pertenece al combo."
                        )
                    }
                )

            normalized.append(
                {
                    "session_index": session_index,
                    "ingredient": ingredient.id,
                }
            )
        return normalized

    def _validate_session_items(self, combo, items):
        if items is None:
            raise ValidationError(
                {"session_items": "session_items es requerido."}
            )

        total_sessions = combo.sessions or 0
        if total_sessions <= 0:
            raise ValidationError({"sessions": "sessions debe ser >= 1."})

        session_counts = {i: 0 for i in range(1, total_sessions + 1)}
        ingredient_ids = {str(obj.id) for obj in combo.ingredients.all()}
        if not ingredient_ids:
            raise ValidationError(
                {"ingredients": "El combo debe tener al menos un ingrediente."}
            )
        used_ingredients = set()
        seen_pairs = set()

        for item in items:
            session_index = item.get("session_index")
            ingredient_id = str(item.get("ingredient"))

            if session_index not in session_counts:
                raise ValidationError(
                    {
                        "session_items": f"session_index inválido: {session_index}."
                    }
                )
            if ingredient_id not in ingredient_ids:
                raise ValidationError(
                    {"session_items": "El ingrediente no pertenece al combo."}
                )

            pair_key = (session_index, ingredient_id)
            if pair_key in seen_pairs:
                raise ValidationError(
                    {
                        "session_items": "No se permiten ingredientes repetidos en la misma sesión."
                    }
                )
            seen_pairs.add(pair_key)
            session_counts[session_index] += 1
            used_ingredients.add(ingredient_id)

        empty_sessions = [idx for idx, count in session_counts.items() if count == 0]
        if empty_sessions:
            raise ValidationError(
                {
                    "session_items": f"Las sesiones sin ingredientes no están permitidas: {empty_sessions}."
                }
            )

        missing_ingredients = sorted(
            ingredient_ids.difference(used_ingredients)
        )
        if missing_ingredients:
            raise ValidationError(
                {
                    "session_items": "Cada ingrediente debe estar en al menos una sesión."
                }
            )

    def _normalize_ordered_list(self, items, field_name, fill_missing_order):
        if items is None:
            return None
        if not isinstance(items, (list, tuple)):
            raise ValidationError({field_name: "Debe ser una lista"})
        normalized = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValidationError({field_name: "Cada elemento debe ser un objeto"})
            if fill_missing_order and item.get("order") is None:
                item = {**item, "order": index}
            normalized.append(item)
        return normalized

    def _parse_id_list(self, raw, field_name):
        if raw is None:
            return None
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception as exc:
                raise ValidationError({field_name: f"JSON inválido: {exc}"})
        return raw

    def _apply_generic_changes(
        self,
        instance,
        model_cls,
        items,
        remove_ids,
        field_name,
        update_fields,
        fill_missing_order,
    ):
        content_type = ContentType.objects.get_for_model(
            instance, for_concrete_model=False
        )
        base_qs = model_cls.objects.filter(
            content_type=content_type, object_id=instance.id
        )
        if remove_ids:
            base_qs.filter(id__in=remove_ids).delete()

        if items is None:
            return

        normalized = self._normalize_ordered_list(
            items, field_name, fill_missing_order
        )
        if not normalized:
            return

        existing = list(base_qs)
        existing_map = {str(obj.id): obj for obj in existing}
        max_order = max([obj.order for obj in existing], default=-1)
        to_create = []
        to_update = []

        for item in normalized:
            if not isinstance(item, dict):
                raise ValidationError({field_name: "Cada elemento debe ser un objeto"})
            item_id = item.get("id")
            payload = dict(item)
            payload.pop("id", None)
            if item_id:
                obj = existing_map.get(str(item_id))
                if not obj:
                    raise ValidationError(
                        {field_name: f"El id {item_id} no pertenece a este item"}
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
                to_create.append(
                    model_cls(
                        content_type=content_type,
                        object_id=instance.id,
                        **payload,
                    )
                )

        if to_create:
            model_cls.objects.bulk_create(to_create)
        if to_update:
            model_cls.objects.bulk_update(to_update, update_fields)
        self._resequence_generic_items(instance, model_cls)

    def _resequence_generic_items(self, instance, model_cls):
        content_type = ContentType.objects.get_for_model(
            instance, for_concrete_model=False
        )
        qs = model_cls.objects.filter(
            content_type=content_type, object_id=instance.id
        ).order_by("order", "created_at", "id")
        to_update = []
        for index, obj in enumerate(qs):
            if obj.order != index:
                obj.order = index
                to_update.append(obj)
        if to_update:
            model_cls.objects.bulk_update(to_update, ["order"])

    def to_internal_value(self, data):
        mutable = data.copy()
        images_order = mutable.get("images_order")
        if "session_items" in mutable:
            mutable["session_items"] = self._parse_json_list(
                mutable.get("session_items"), "session_items"
            )
        if "ingredients" in mutable:
            parsed_ing = self._parse_ingredients(mutable.get("ingredients"))
            if hasattr(mutable, "setlist") and isinstance(parsed_ing, list):
                mutable.setlist("ingredients", parsed_ing)
            else:
                mutable["ingredients"] = parsed_ing
        if "benefits" in mutable:
            mutable["benefits"] = self._parse_json_list(
                mutable.get("benefits"), "benefits"
            )
        if "recommended_points" in mutable:
            mutable["recommended_points"] = self._parse_json_list(
                mutable.get("recommended_points"), "recommended_points"
            )
        if "faqs" in mutable:
            mutable["faqs"] = self._parse_json_list(mutable.get("faqs"), "faqs")
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
        if "uploaded_images" in mutable:
            cleaned = self._clean_uploaded_images(mutable.get("uploaded_images"))
            if cleaned is None:
                mutable.pop("uploaded_images", None)
            else:
                if hasattr(mutable, "setlist"):
                    mutable.setlist("uploaded_images", cleaned)
                else:
                    mutable["uploaded_images"] = cleaned
        if images_order is not None:
            parsed_order = self._parse_images_order(images_order)
            self.context["images_order"] = parsed_order
            files_map, plain_list = self._extract_uploaded_map(data)
            self.context["uploaded_map"] = files_map
            self.context["uploaded_list"] = plain_list
            if hasattr(mutable, "setlist"):
                mutable.setlist("images_order", parsed_order)
            else:
                mutable["images_order"] = parsed_order
        return super().to_internal_value(mutable)

    def _parse_images_order(self, raw):
        if raw is None:
            return None
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception as exc:
                raise ValidationError({"images_order": f"JSON inválido: {exc}"})
        if not isinstance(raw, (list, tuple)):
            raise ValidationError({"images_order": "Debe ser una lista"})
        normalized = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValidationError(
                    {"images_order": "Cada elemento debe ser un objeto con id o upload_key"}
                )
            img_id = item.get("id")
            upload_key = item.get("upload_key")
            if not img_id and not upload_key:
                raise ValidationError(
                    {"images_order": "Cada elemento debe tener 'id' o 'upload_key'"}
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
                if key.startswith("uploaded_images[") and key.endswith("]"):
                    upload_key = key[len("uploaded_images[") : -1]
                    files_map[upload_key] = request.FILES.get(key)
        plain_list = []
        if request and hasattr(request, "FILES"):
            plain_list = request.FILES.getlist("uploaded_images")
        return files_map, plain_list

    def _apply_mixed_order(self, combo, images_order, uploaded_map, uploaded_list):
        existing_qs = list(combo.images.all())
        existing_map = {str(img.id): img for img in existing_qs}
        used_ids = set()
        new_objs = []
        final_existing = []
        plain_iter = iter(uploaded_list or [])

        for idx, item in enumerate(images_order):
            img_id = item.get("id")
            upload_key = item.get("upload_key")
            if img_id:
                img = existing_map.get(str(img_id))
                if not img:
                    raise ValidationError(
                        {"images_order": f"Imagen {img_id} no pertenece al combo"}
                    )
                used_ids.add(str(img_id))
                img.order = idx
                final_existing.append(img)
            elif upload_key:
                file = uploaded_map.get(upload_key)
                if not file:
                    try:
                        file = next(plain_iter)
                    except StopIteration:
                        raise ValidationError(
                            {"images_order": f"No se encontró archivo para upload_key '{upload_key}'"}
                        )
                new_objs.append(ComboImage(combo=combo, image=file, order=idx))

        tail = [img for img in existing_qs if str(img.id) not in used_ids]
        order_start = len(images_order)
        for offset, img in enumerate(tail):
            img.order = order_start + offset
            final_existing.append(img)

        if new_objs:
            ComboImage.objects.bulk_create(new_objs)
        if final_existing:
            ComboImage.objects.bulk_update(final_existing, ["order"])

    def get_cover_image(self, obj):
        first_img = obj.images.first()
        if first_img:
            return first_img.image.url
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
        ingredients = validated_data.pop("ingredients", [])
        session_items = validated_data.pop("session_items", None)
        uploaded_images = validated_data.pop("uploaded_images", [])
        images_order = validated_data.pop("images_order", None)
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
                [],
                "faqs",
                ["question", "answer", "order"],
                True,
            )
            if images_order is not None:
                self._apply_mixed_order(combo, images_order, uploaded_map, uploaded_list)
            elif uploaded_images:
                self._create_images(combo, uploaded_images)
            if ingredients:
                self._save_ingredients(combo, ingredients)
            if session_items is None:
                raise ValidationError(
                    {"session_items": "session_items es requerido."}
                )
            normalized_session_items = self._normalize_session_items(
                combo, session_items
            )
            self._validate_session_items(combo, normalized_session_items)
            combo.session_items.all().delete()
            if normalized_session_items:
                self._save_session_items(combo, normalized_session_items)
            return combo

    def update(self, instance, validated_data):
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
        session_items = validated_data.pop("session_items", None)
        uploaded_images = validated_data.pop("uploaded_images", [])
        removed_ids = validated_data.pop("removed_image_ids", [])
        ordered_ids = validated_data.pop("ordered_ids", [])
        images_order = validated_data.pop("images_order", None)
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
                combo.images.filter(id__in=removed_ids).delete()
            if images_order is not None:
                self._apply_mixed_order(combo, images_order, uploaded_map, uploaded_list)
            if uploaded_images:
                self._create_images(combo, uploaded_images)
            if ingredients is not None:
                instance.ingredients.all().delete()
                if ingredients:
                    self._save_ingredients(instance, ingredients)
            if session_items is not None:
                normalized_session_items = self._normalize_session_items(
                    instance, session_items
                )
                self._validate_session_items(instance, normalized_session_items)
                instance.session_items.all().delete()
                if normalized_session_items:
                    self._save_session_items(instance, normalized_session_items)
            else:
                existing_items = [
                    {"session_index": obj.session_index, "ingredient": obj.ingredient_id}
                    for obj in instance.session_items.all()
                ]
                if not existing_items:
                    raise ValidationError(
                        {"session_items": "session_items es requerido."}
                    )
                self._validate_session_items(instance, existing_items)
            if ordered_ids:
                reorder_gallery(combo, ordered_ids)
            return combo


class PublicComboSerializer(ComboSerializer):
    category = serializers.SerializerMethodField()
    journey = serializers.SerializerMethodField()
    ingredients = serializers.SerializerMethodField()
    zones = serializers.SerializerMethodField()

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
            "treatment_types",
            "objectives",
            "intensities",
            "price",
            "promotional_price",
            "sessions",
            "min_session_interval_days",
            "duration",
            "ingredients",
            "zones",
            "images",
            "benefits",
            "recommended_points",
            "faqs",
            "cover_image",
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
