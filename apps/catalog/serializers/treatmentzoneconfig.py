from ..models import TreatmentZoneConfig
from .base import UUIDSerializer


class TreatmentZoneConfigSerializer(UUIDSerializer):
    class Meta:
        model = TreatmentZoneConfig
        fields = "__all__"
