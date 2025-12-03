from ..models import TreatmentZoneConfig
from .base import UUIDSerializer


class TreatmentZoneConfigSerializer(UUIDSerializer):
    class Meta:
        model = TreatmentZoneConfig
        fields = "__all__"
        extra_kwargs = {
            # Se asigna automaticamente desde TreatmentSerializer; no se pide en payload.
            "treatment": {"read_only": True},
        }
