from ..models import Journey
from .base import UUIDSerializer


class JourneySerializer(UUIDSerializer):
    class Meta:
        model = Journey
        fields = "__all__"
