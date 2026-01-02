import json
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ..models import Combo, ComboIngredient, ComboStep, ComboStepItem, ComboImage
from ..services.pricing import effective_price_for_combo
from ..utils.gallery import reorder_gallery
from .base import UUIDSerializer
from .gallery import ComboImageSerializer
from .fields import TagListField


class ComboIngredientSerializer(UUIDSerializer):
    class Meta:
        model = ComboIngredient
        fields = "__all__"
        extra_kwargs = {"combo": {"read_only": True}}


class ComboStepItemSerializer(UUIDSerializer):
    class Meta:
        model = ComboStepItem
        fields = "__all__"


class ComboStepSerializer(UUIDSerializer):
    items = ComboStepItemSerializer(many=True, read_only=True)

    class Meta:
        model = ComboStep
        fields = "__all__"


class ComboSerializer(UUIDSerializer):
    ingredients = ComboIngredientSerializer(many=True, required=False)
    steps = ComboStepSerializer(many=True, required=False, read_only=True)
    images = ComboImageSerializer(many=True, read_only=True)
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

    class Meta:
        model = Combo
        fields = "__all__"

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

    def to_internal_value(self, data):
        mutable = data.copy()
        images_order = mutable.get("images_order")
        if "ingredients" in mutable:
            parsed_ing = self._parse_ingredients(mutable.get("ingredients"))
            if hasattr(mutable, "setlist") and isinstance(parsed_ing, list):
                mutable.setlist("ingredients", parsed_ing)
            else:
                mutable["ingredients"] = parsed_ing
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
        ingredients = validated_data.pop("ingredients", [])
        uploaded_images = validated_data.pop("uploaded_images", [])
        images_order = validated_data.pop("images_order", None)
        uploaded_map = self.context.get("uploaded_map", {})
        uploaded_list = self.context.get("uploaded_list", [])
        with transaction.atomic():
            combo = super().create(validated_data)
            if tags is not None:
                combo.tags.set(tags)
            if images_order is not None:
                self._apply_mixed_order(combo, images_order, uploaded_map, uploaded_list)
            elif uploaded_images:
                self._create_images(combo, uploaded_images)
            if ingredients:
                self._save_ingredients(combo, ingredients)
            return combo

    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)
        ingredients = validated_data.pop("ingredients", None)
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
            if ordered_ids:
                reorder_gallery(combo, ordered_ids)
            return combo
