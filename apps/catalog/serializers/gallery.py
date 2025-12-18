from rest_framework import serializers

from ..models import TreatmentImage, ComboImage, JourneyImage
from .base import UUIDSerializer


class TreatmentImageSerializer(UUIDSerializer):
    class Meta:
        model = TreatmentImage
        fields = ["id", "image", "alt_text", "order"]


class ComboImageSerializer(UUIDSerializer):
    class Meta:
        model = ComboImage
        fields = ["id", "image", "alt_text", "order"]


class JourneyImageSerializer(UUIDSerializer):
    class Meta:
        model = JourneyImage
        fields = ["id", "image", "alt_text", "order"]
