from rest_framework import serializers
from ..models import TreatmentZoneIncompatibility
from .base import UUIDSerializer


class TreatmentZoneIncompatibilitySerializer(UUIDSerializer):
    left_tzc = serializers.UUIDField(source="left_tzc_id", read_only=True)
    right_tzc = serializers.UUIDField(source="right_tzc_id", read_only=True)
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
