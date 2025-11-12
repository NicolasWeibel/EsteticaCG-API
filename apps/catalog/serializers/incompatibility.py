from rest_framework import serializers
from ..models import TreatmentZoneIncompatibility, TreatmentZoneConfig
from .base import UUIDSerializer


class TreatmentZoneConfigCompactSerializer(UUIDSerializer):
    """Compacto: para mostrar en incompatibilidades con nombre legible"""

    label = serializers.SerializerMethodField()

    class Meta:
        model = TreatmentZoneConfig
        fields = ["id", "label"]

    def get_label(self, obj):
        return f"{obj.treatment.title} / {obj.zone.name} / {obj.body_position or 'N/A'}"


class TreatmentZoneIncompatibilitySerializer(UUIDSerializer):
    left_tzc = TreatmentZoneConfigCompactSerializer(read_only=True)
    right_tzc = TreatmentZoneConfigCompactSerializer(read_only=True)
    left_tzc_id = serializers.UUIDField(write_only=True)
    right_tzc_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = TreatmentZoneIncompatibility
        fields = [
            "id",
            "left_tzc",
            "right_tzc",
            "left_tzc_id",
            "right_tzc_id",
            "created_at",
        ]
