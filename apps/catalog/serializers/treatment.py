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
from ..utils.gallery import reorder_gallery
from .gallery import TreatmentMediaSerializer
from .item_content import (
    ItemBenefitSerializer,
    ItemRecommendedPointSerializer,
    ItemFAQSerializer,
)
from .treatmentzoneconfig import TreatmentZoneConfigSerializer
from .fields import TagListField
from .base import UUIDSerializer
from .media import MediaUploadMixin
from .utils import clean_uploaded_media, parse_json_list
from .item_content_sync import GenericItemContentSyncMixin
from ..utils.media import build_media_url
from .filters import TechniqueSerializer, ObjectiveSerializer, IntensitySerializer


class TreatmentSerializer(
    GenericItemContentSyncMixin, MediaUploadMixin, UUIDSerializer
):
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

    def _create_media(self, treatment, media):
        start = treatment.media.count()
        to_create = []
        for index, media_file in enumerate(media, start=start):
            media_type = self._media_type_for_file(media_file)
            to_create.append(
                TreatmentMedia(
                    treatment=treatment,
                    media=media_file,
                    media_type=media_type,
                    order=index,
                )
            )
        if to_create:
            TreatmentMedia.objects.bulk_create(to_create)

    def _parse_zone_configs(self, raw):
        if raw is None:
            return None
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception as exc:
                raise ValidationError({"zone_configs": f"JSON inválido: {exc}"})
        if hasattr(raw, "read"):
            try:
                content = raw.read()
                if hasattr(raw, "seek"):
                    raw.seek(0)
                return json.loads(content)
            except Exception as exc:
                raise ValidationError({"zone_configs": f"JSON inválido: {exc}"})
        return raw

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

    def _extract_uploaded_map(self, data):
        """
        Busca archivos con nombre uploaded_media[<key>] en request.FILES
        y arma un dict upload_key -> file.
        """
        request = self.context.get("request")
        files_map = {}
        if request and hasattr(request, "FILES"):
            for key in request.FILES:
                if key.startswith("uploaded_media[") and key.endswith("]"):
                    upload_key = key[len("uploaded_media[") : -1]
                    files_map[upload_key] = request.FILES.get(key)
        # fallback: si viene lista simple y hay media_order con upload_key, intentar mapear en orden
        plain_list = []
        if request and hasattr(request, "FILES"):
            plain_list = request.FILES.getlist("uploaded_media")
        return files_map, plain_list

    def to_internal_value(self, data):
        mutable = data.copy()
        media_order = mutable.get("media_order")
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

    def _apply_mixed_order(self, treatment, media_order, uploaded_map, uploaded_list):
        """
        Reordena y crea nuevos medios según media_order.
        """
        existing_qs = list(treatment.media.all())
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
                        {"media_order": f"Media {media_id} no pertenece al tratamiento"}
                    )
                used_ids.add(str(media_id))
                media_obj.order = idx
                final_existing.append(media_obj)
            elif upload_key:
                file = uploaded_map.get(upload_key)
                if not file:
                    # fallback: tomar siguiente de la lista simple
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
                    TreatmentMedia(
                        treatment=treatment,
                        media=file,
                        media_type=media_type,
                        order=idx,
                    )
                )

        # agregar existentes que no se mencionaron, al final
        tail = [item for item in existing_qs if str(item.id) not in used_ids]
        order_start = len(media_order)
        for offset, media_obj in enumerate(tail):
            media_obj.order = order_start + offset
            final_existing.append(media_obj)

        if new_objs:
            TreatmentMedia.objects.bulk_create(new_objs)
        if final_existing:
            TreatmentMedia.objects.bulk_update(final_existing, ["order"])

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

            # Si no hay id pero la zona ya existe, actualizarla en vez de crear
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
        uploaded_media = validated_data.pop("uploaded_media", [])
        removed_ids = validated_data.pop("removed_media_ids", [])
        ordered_media_ids = validated_data.pop("ordered_media_ids", [])
        media_order = validated_data.pop("media_order", None)
        uploaded_map = self.context.get("uploaded_map", {})
        uploaded_list = self.context.get("uploaded_list", [])
        with transaction.atomic():
            treatment = super().create(validated_data)
            if tags is not None:
                treatment.tags.set(tags)
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
            if removed_ids:
                treatment.media.filter(id__in=removed_ids).delete()
            if media_order is not None:
                self._apply_mixed_order(
                    treatment, media_order, uploaded_map, uploaded_list
                )
            elif uploaded_media:
                self._create_media(treatment, uploaded_media)
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
        uploaded_media = validated_data.pop("uploaded_media", [])
        removed_ids = validated_data.pop("removed_media_ids", [])
        ordered_media_ids = validated_data.pop("ordered_media_ids", [])
        media_order = validated_data.pop("media_order", None)
        uploaded_map = self.context.get("uploaded_map", {})
        uploaded_list = self.context.get("uploaded_list", [])
        with transaction.atomic():
            treatment = super().update(instance, validated_data)
            if tags is not None:
                treatment.tags.set(tags)
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
            if removed_ids:
                treatment.media.filter(id__in=removed_ids).delete()
            if media_order is not None:
                self._apply_mixed_order(
                    treatment, media_order, uploaded_map, uploaded_list
                )
            elif uploaded_media:
                self._create_media(treatment, uploaded_media)
            if zone_configs is not None:
                self._sync_zone_configs(treatment, zone_configs)
            if was_active and not treatment.is_active:
                cleanup_treatment_deactivation([treatment.id])
        if ordered_media_ids:
            reorder_gallery(treatment, ordered_media_ids)
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
