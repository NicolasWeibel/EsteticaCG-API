from rest_framework import viewsets
from ..models import TreatmentZoneConfig
from ..serializers.treatmentzoneconfig import TreatmentZoneConfigSerializer
from ..permissions import IsAdminOrReadOnly


class TreatmentZoneConfigViewSet(viewsets.ModelViewSet):
    queryset = TreatmentZoneConfig.objects.all()
    serializer_class = TreatmentZoneConfigSerializer
    permission_classes = [IsAdminOrReadOnly]
