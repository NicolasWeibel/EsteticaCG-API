import json
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ..models import Journey, JourneyImage
from ..services.pricing import effective_price_for_journey
from ..utils.gallery import reorder_gallery
from .base import UUIDSerializer
from .gallery import JourneyImageSerializer


class JourneySerializer(UUIDSerializer):
    images = JourneyImageSerializer(many=True, read_only=True)
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
        model = Journey
        fields = "__all__"

    def get_cover_image(self, obj):
        first_img = obj.images.first()
        if first_img:
            return first_img.image.url
        return None

    def get_effective_price(self, obj):
        return effective_price_for_journey(obj)

    def get_kind(self, obj):
        return "journey"

    def _create_images(self, journey, images):
        start = journey.images.count()
        to_create = []
        for index, img_file in enumerate(images, start=start):
            to_create.append(JourneyImage(journey=journey, image=img_file, order=index))
        if to_create:
            JourneyImage.objects.bulk_create(to_create)

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

    def _apply_mixed_order(self, journey, images_order, uploaded_map, uploaded_list):
        existing_qs = list(journey.images.all())
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
                        {"images_order": f"Imagen {img_id} no pertenece a la jornada"}
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
                new_objs.append(JourneyImage(journey=journey, image=file, order=idx))

        tail = [img for img in existing_qs if str(img.id) not in used_ids]
        order_start = len(images_order)
        for offset, img in enumerate(tail):
            img.order = order_start + offset
            final_existing.append(img)

        if new_objs:
            JourneyImage.objects.bulk_create(new_objs)
        if final_existing:
            JourneyImage.objects.bulk_update(final_existing, ["order"])

    def create(self, validated_data):
        uploaded_images = validated_data.pop("uploaded_images", [])
        images_order = validated_data.pop("images_order", None)
        uploaded_map = self.context.get("uploaded_map", {})
        uploaded_list = self.context.get("uploaded_list", [])
        journey = super().create(validated_data)
        if images_order is not None:
            self._apply_mixed_order(journey, images_order, uploaded_map, uploaded_list)
        elif uploaded_images:
            self._create_images(journey, uploaded_images)
        return journey

    def update(self, instance, validated_data):
        uploaded_images = validated_data.pop("uploaded_images", [])
        removed_ids = validated_data.pop("removed_image_ids", [])
        ordered_ids = validated_data.pop("ordered_ids", [])
        images_order = validated_data.pop("images_order", None)
        uploaded_map = self.context.get("uploaded_map", {})
        uploaded_list = self.context.get("uploaded_list", [])
        journey = super().update(instance, validated_data)
        if removed_ids:
            journey.images.filter(id__in=removed_ids).delete()
        if images_order is not None:
            self._apply_mixed_order(journey, images_order, uploaded_map, uploaded_list)
        elif uploaded_images:
            self._create_images(journey, uploaded_images)
        if ordered_ids:
            reorder_gallery(journey, ordered_ids)
        return journey
