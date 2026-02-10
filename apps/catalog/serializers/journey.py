import json
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ..models import Journey, JourneyMedia
from ..services.pricing import effective_price_for_journey
from ..utils.gallery import reorder_gallery
from .base import UUIDSerializer
from .gallery import JourneyMediaSerializer
from .media import MediaUploadMixin
from ..utils.media import build_media_url


class JourneySerializer(MediaUploadMixin, UUIDSerializer):
    media = JourneyMediaSerializer(many=True, read_only=True)
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

    class Meta:
        model = Journey
        fields = "__all__"

    def get_cover_media(self, obj):
        first_media = obj.media.first()
        if first_media:
            return build_media_url(first_media.media, first_media.media_type)
        return None

    def get_effective_price(self, obj):
        return effective_price_for_journey(obj)

    def get_kind(self, obj):
        return "journey"

    def _create_media(self, journey, media):
        start = journey.media.count()
        to_create = []
        for index, media_file in enumerate(media, start=start):
            media_type = self._media_type_for_file(media_file)
            to_create.append(
                JourneyMedia(
                    journey=journey,
                    media=media_file,
                    media_type=media_type,
                    order=index,
                )
            )
        if to_create:
            JourneyMedia.objects.bulk_create(to_create)

    def _clean_uploaded_media(self, raw):
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
        media_order = mutable.get("media_order")
        if "uploaded_media" in mutable:
            cleaned = self._clean_uploaded_media(mutable.get("uploaded_media"))
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
                    {"media_order": "Cada elemento debe ser un objeto con id o upload_key"}
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

    def _apply_mixed_order(self, journey, media_order, uploaded_map, uploaded_list):
        existing_qs = list(journey.media.all())
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
                        {"media_order": f"Media {media_id} no pertenece a la jornada"}
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
                            {"media_order": f"No se encontró archivo para upload_key '{upload_key}'"}
                        )
                media_type = self._media_type_for_file(file)
                new_objs.append(
                    JourneyMedia(
                        journey=journey,
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
            JourneyMedia.objects.bulk_create(new_objs)
        if final_existing:
            JourneyMedia.objects.bulk_update(final_existing, ["order"])

    def create(self, validated_data):
        uploaded_media = validated_data.pop("uploaded_media", [])
        media_order = validated_data.pop("media_order", None)
        uploaded_map = self.context.get("uploaded_map", {})
        uploaded_list = self.context.get("uploaded_list", [])
        journey = super().create(validated_data)
        if media_order is not None:
            self._apply_mixed_order(journey, media_order, uploaded_map, uploaded_list)
        elif uploaded_media:
            self._create_media(journey, uploaded_media)
        return journey

    def update(self, instance, validated_data):
        uploaded_media = validated_data.pop("uploaded_media", [])
        removed_ids = validated_data.pop("removed_media_ids", [])
        ordered_media_ids = validated_data.pop("ordered_media_ids", [])
        media_order = validated_data.pop("media_order", None)
        uploaded_map = self.context.get("uploaded_map", {})
        uploaded_list = self.context.get("uploaded_list", [])
        journey = super().update(instance, validated_data)
        if removed_ids:
            journey.media.filter(id__in=removed_ids).delete()
        if media_order is not None:
            self._apply_mixed_order(journey, media_order, uploaded_map, uploaded_list)
        elif uploaded_media:
            self._create_media(journey, uploaded_media)
        if ordered_media_ids:
            reorder_gallery(journey, ordered_media_ids)
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
            "category",
            "default_sort",
            "addons",
            "media",
            "cover_media",
            "effective_price",
            "kind",
        ]

    def get_category(self, obj):
        category = getattr(obj, "category", None)
        if not category:
            return None
        return {"id": category.id, "name": category.name, "slug": category.slug}

