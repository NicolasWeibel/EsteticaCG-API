import json
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ..models import Treatment, TreatmentImage
from ..services.pricing import effective_price_for_treatment
from ..utils.gallery import reorder_gallery
from .gallery import TreatmentImageSerializer
from .treatmentzoneconfig import TreatmentZoneConfigSerializer
from .fields import TagListField
from .base import UUIDSerializer


class TreatmentSerializer(UUIDSerializer):
    zone_configs = TreatmentZoneConfigSerializer(many=True, required=False)
    images = TreatmentImageSerializer(many=True, read_only=True)
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
        model = Treatment
        fields = "__all__"

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

    def _clean_uploaded_images(self, raw):
        """
        Acepta solo archivos; si llegan strings/URLs los ignora para evitar
        que el serializer interprete cada carácter como un item de la lista.
        """
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
        if "zone_configs" in mutable:
            mutable["zone_configs"] = self._parse_zone_configs(
                mutable.get("zone_configs")
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
        return super().to_internal_value(mutable)

    def validate(self, attrs):
        zone_configs = attrs.get("zone_configs")
        requires_zones = attrs.get(
            "requires_zones",
            self.instance.requires_zones if self.instance else False,
        )

        if requires_zones:
            has_zones = (
                bool(zone_configs)
                if zone_configs is not None
                else bool(self.instance and self.instance.zone_configs.exists())
            )
            if not has_zones:
                raise serializers.ValidationError(
                    {
                        "zone_configs": "Este tratamiento requiere al menos una zona configurada."
                    }
                )
        return attrs

    def get_cover_image(self, obj):
        first_img = obj.images.first()
        if first_img:
            return first_img.image.url
        return None

    def get_effective_price(self, obj):
        return effective_price_for_treatment(obj)

    def get_kind(self, obj):
        return "treatment"

    def _create_images(self, treatment, images):
        start = treatment.images.count()
        to_create = []
        for index, img_file in enumerate(images, start=start):
            to_create.append(
                TreatmentImage(treatment=treatment, image=img_file, order=index)
            )
        if to_create:
            TreatmentImage.objects.bulk_create(to_create)

    def _clean_uploaded_images(self, raw):
        """
        Mantiene compatibilidad con el payload actual, pero descarta strings.
        """
        if raw is None:
            return None
        if hasattr(raw, "read"):
            return [raw]
        if isinstance(raw, str):
            return []
        if isinstance(raw, (list, tuple)):
            return [item for item in raw if hasattr(item, "read")]
        return []

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
        """
        Busca archivos con nombre uploaded_images[<key>] en request.FILES
        y arma un dict upload_key -> file.
        """
        request = self.context.get("request")
        files_map = {}
        if request and hasattr(request, "FILES"):
            for key in request.FILES:
                if key.startswith("uploaded_images[") and key.endswith("]"):
                    upload_key = key[len("uploaded_images[") : -1]
                    files_map[upload_key] = request.FILES.get(key)
        # fallback: si viene lista simple y hay images_order con upload_key, intentar mapear en orden
        plain_list = []
        if request and hasattr(request, "FILES"):
            plain_list = request.FILES.getlist("uploaded_images")
        return files_map, plain_list

    def to_internal_value(self, data):
        mutable = data.copy()
        images_order = mutable.get("images_order")
        if "zone_configs" in mutable:
            mutable["zone_configs"] = self._parse_zone_configs(
                mutable.get("zone_configs")
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

    def _apply_mixed_order(self, treatment, images_order, uploaded_map, uploaded_list):
        """
        Reordena y crea nuevas imágenes según images_order.
        """
        existing_qs = list(treatment.images.all())
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
                        {"images_order": f"Imagen {img_id} no pertenece al tratamiento"}
                    )
                used_ids.add(str(img_id))
                img.order = idx
                final_existing.append(img)
            elif upload_key:
                file = uploaded_map.get(upload_key)
                if not file:
                    # fallback: tomar siguiente de la lista simple
                    try:
                        file = next(plain_iter)
                    except StopIteration:
                        raise ValidationError(
                            {"images_order": f"No se encontró archivo para upload_key '{upload_key}'"}
                        )
                new_objs.append(
                    TreatmentImage(treatment=treatment, image=file, order=idx)
                )

        # agregar existentes que no se mencionaron, al final
        tail = [
            img for img in existing_qs if str(img.id) not in used_ids
        ]
        order_start = len(images_order)
        for offset, img in enumerate(tail):
            img.order = order_start + offset
            final_existing.append(img)

        if new_objs:
            TreatmentImage.objects.bulk_create(new_objs)
        if final_existing:
            TreatmentImage.objects.bulk_update(final_existing, ["order"])

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

    def create(self, validated_data):
        tags = validated_data.pop("tags", None)
        zone_configs = validated_data.pop("zone_configs", [])
        uploaded_images = validated_data.pop("uploaded_images", [])
        images_order = validated_data.pop("images_order", None)
        uploaded_map = self.context.get("uploaded_map", {})
        uploaded_list = self.context.get("uploaded_list", [])
        with transaction.atomic():
            treatment = super().create(validated_data)
            if tags is not None:
                treatment.tags.set(tags)
            if images_order is not None:
                self._apply_mixed_order(treatment, images_order, uploaded_map, uploaded_list)
            elif uploaded_images:
                self._create_images(treatment, uploaded_images)
            if zone_configs:
                self._save_zone_configs(treatment, zone_configs)
            return treatment

    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)
        zone_configs = validated_data.pop("zone_configs", None)
        uploaded_images = validated_data.pop("uploaded_images", [])
        removed_ids = validated_data.pop("removed_image_ids", [])
        ordered_ids = validated_data.pop("ordered_ids", [])
        images_order = validated_data.pop("images_order", None)
        uploaded_map = self.context.get("uploaded_map", {})
        uploaded_list = self.context.get("uploaded_list", [])
        with transaction.atomic():
            treatment = super().update(instance, validated_data)
            if tags is not None:
                treatment.tags.set(tags)
            if removed_ids:
                treatment.images.filter(id__in=removed_ids).delete()
            if images_order is not None:
                self._apply_mixed_order(treatment, images_order, uploaded_map, uploaded_list)
            elif uploaded_images:
                self._create_images(treatment, uploaded_images)
            if zone_configs is not None:
                treatment.zone_configs.all().delete()
                if zone_configs:
                    self._save_zone_configs(treatment, zone_configs)
            if ordered_ids:
                reorder_gallery(treatment, ordered_ids)
            return treatment
