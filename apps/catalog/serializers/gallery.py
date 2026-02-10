from rest_framework import serializers

from ..models import TreatmentMedia, ComboMedia, JourneyMedia
from .base import UUIDSerializer
from ..utils.media import build_media_url


class TreatmentMediaSerializer(UUIDSerializer):
    media = serializers.SerializerMethodField()

    class Meta:
        model = TreatmentMedia
        fields = ["id", "media", "media_type", "alt_text", "order"]

    def get_media(self, obj):
        return build_media_url(obj.media, obj.media_type)


class ComboMediaSerializer(UUIDSerializer):
    media = serializers.SerializerMethodField()

    class Meta:
        model = ComboMedia
        fields = ["id", "media", "media_type", "alt_text", "order"]

    def get_media(self, obj):
        return build_media_url(obj.media, obj.media_type)


class JourneyMediaSerializer(UUIDSerializer):
    media = serializers.SerializerMethodField()

    class Meta:
        model = JourneyMedia
        fields = ["id", "media", "media_type", "alt_text", "order"]

    def get_media(self, obj):
        return build_media_url(obj.media, obj.media_type)
