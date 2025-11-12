from ..models import Treatment
from .treatmentzoneconfig import TreatmentZoneConfigSerializer
from .base import UUIDSerializer


class TreatmentSerializer(UUIDSerializer):
    zone_configs = TreatmentZoneConfigSerializer(many=True, required=False)

    class Meta:
        model = Treatment
        fields = "__all__"
