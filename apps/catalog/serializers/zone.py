from ..models import Zone
from .base import UUIDSerializer


class ZoneSerializer(UUIDSerializer):
    class Meta:
        model = Zone
        fields = "__all__"
