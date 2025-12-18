from django.db import transaction
from rest_framework import serializers

from ..models import Treatment, TreatmentImage
from .gallery import TreatmentImageSerializer
from .treatmentzoneconfig import TreatmentZoneConfigSerializer
from .base import UUIDSerializer


class TreatmentSerializer(UUIDSerializer):
    zone_configs = TreatmentZoneConfigSerializer(many=True, required=False)
    images = TreatmentImageSerializer(many=True, read_only=True)
    cover_image = serializers.SerializerMethodField()
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False, use_url=False),
        write_only=True,
        required=False,
    )

    class Meta:
        model = Treatment
        fields = "__all__"

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

    def _create_images(self, treatment, images):
        start = treatment.images.count()
        to_create = []
        for index, img_file in enumerate(images, start=start):
            to_create.append(
                TreatmentImage(treatment=treatment, image=img_file, order=index)
            )
        if to_create:
            TreatmentImage.objects.bulk_create(to_create)

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
        zone_configs = validated_data.pop("zone_configs", [])
        uploaded_images = validated_data.pop("uploaded_images", [])
        with transaction.atomic():
            treatment = super().create(validated_data)
            if uploaded_images:
                self._create_images(treatment, uploaded_images)
            if zone_configs:
                self._save_zone_configs(treatment, zone_configs)
            return treatment

    def update(self, instance, validated_data):
        zone_configs = validated_data.pop("zone_configs", None)
        uploaded_images = validated_data.pop("uploaded_images", [])
        with transaction.atomic():
            treatment = super().update(instance, validated_data)
            if uploaded_images:
                self._create_images(treatment, uploaded_images)
            if zone_configs is not None:
                treatment.zone_configs.all().delete()
                if zone_configs:
                    self._save_zone_configs(treatment, zone_configs)
            return treatment
